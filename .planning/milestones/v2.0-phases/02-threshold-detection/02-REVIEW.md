---
phase: 02-threshold-detection
reviewed: 2026-05-08T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - cli/main.py
  - core/threshold_manager.py
  - monitoring/orchestrator.py
  - tests/test_threshold_manager.py
  - ui/display_controller.py
  - ui/session_display.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed six files covering the Phase 2 threshold detection feature: `ThresholdState` dataclass, `get_threshold()` in `core/threshold_manager.py`, integration in `monitoring/orchestrator.py`, pass-through in `ui/display_controller.py`, and rendering in `ui/session_display.py`. The test suite in `tests/test_threshold_manager.py` was also reviewed.

The core threshold logic and the orchestrator wiring are sound. The decision order (manual → calibrating → auto) is correctly implemented and the frozen dataclass prevents accidental mutation. The display pipeline correctly suppresses OVERAGE/INCLUDED rows during calibration.

Four warnings were found: a vacuous test assertion that gives false confidence, a redundant double-P90 computation per monitoring cycle, a `**kwargs` sink in `session_display` that silently drops misspelled keys, and an unbounded config file read on every cycle. Four info items cover dead code, import fragility, a confusing redundant variable lookup, and a missing test scenario.

No critical (security/crash/data-loss) issues were found.

---

## Warnings

### WR-01: Vacuous test assertion gives false confidence

**File:** `tests/test_threshold_manager.py:94`
**Issue:** The assertion `assert "overage_threshold_tokens" in caplog.text or len(caplog.records) >= 0` is always `True` because `len(caplog.records) >= 0` is unconditionally true for any list. The warning-log check for the zero-value case can never fail, so the test passes even if the warning is silently removed from the implementation.

**Fix:**
```python
# Remove the vacuous fallback — assert the warning was actually logged
assert "overage_threshold_tokens" in caplog.text
```

---

### WR-02: Double P90 computation per monitoring cycle for custom plan

**File:** `monitoring/orchestrator.py:171-184`
**Issue:** For the `custom` plan, `_calculate_token_limit()` (line 171) calls `get_token_limit(plan, blocks)`, which internally invokes `P90Calculator` to compute a P90. Then on line 177, `get_threshold(blocks)` constructs a second `P90Calculator` instance and computes a second P90 over the same blocks. Each `P90Calculator()` call creates a new instance with its own `lru_cache`, so the cache does not deduplicate across these two calls. The two results may also diverge if the implementations ever drift.

**Fix:** Pass the already-computed `threshold_state.threshold_tokens` directly as the `token_limit` for the `auto` / `manual` cases, and remove the separate `_calculate_token_limit` call for the `custom` plan. The orchestrator already overrides `token_limit` from `threshold_state` at lines 181-184; `_calculate_token_limit` for `custom` is therefore redundant:
```python
# In _fetch_and_process_data, for custom plan:
threshold_state = get_threshold(blocks)
if threshold_state.status == "calibrating":
    token_limit = DEFAULT_TOKEN_LIMIT
elif threshold_state.threshold_tokens is not None:
    token_limit = threshold_state.threshold_tokens
# Remove the separate _calculate_token_limit(data) call for custom plan,
# or guard it: only call _calculate_token_limit when plan != "custom".
```

---

### WR-03: `**kwargs` sink in `format_active_session_screen` silently drops unknown keys

**File:** `ui/session_display.py:154`
**Issue:** `format_active_session_screen` declares `**kwargs` and pulls `threshold_state` and `cost_limit_p90` from it via `.get()`. If either key is misspelled at any call site (e.g., `threashold_state=...`), the method silently defaults to `None` and the threshold rows are never rendered — with no error, no log, and no test failure to catch it. The current call site in `display_controller.py:281` uses the correct key, but the contract is not enforced.

**Fix:** Accept `threshold_state` as an explicit keyword argument with a default:
```python
def format_active_session_screen(
    self,
    plan: str,
    ...
    original_limit: int = 0,
    threshold_state: Optional["ThresholdState"] = None,
    cost_limit_p90: Optional[float] = None,
    messages_limit_p90: Optional[int] = None,
) -> list[str]:
```
This makes misspellings a `TypeError` caught immediately at runtime, and makes the interface self-documenting.

---

### WR-04: Unbounded config.json read on every monitoring cycle

**File:** `core/threshold_manager.py:37`
**Issue:** `_read_manual_override()` opens and fully reads `config.json` with no size limit. This function is called by `get_threshold()`, which is called on every `_fetch_and_process_data()` cycle (default: every 10 seconds). A malformed or excessively large file at `~/.claude-monitor/config.json` will be fully read into memory on each cycle. While the exception is caught, it means each cycle silently fails for the duration of the problem.

**Fix:** Add a size guard before reading:
```python
MAX_CONFIG_SIZE = 1 * 1024 * 1024  # 1 MB sanity limit
if config_file.stat().st_size > MAX_CONFIG_SIZE:
    logger.warning(
        "config.json exceeds size limit (%d bytes) — falling back to P90",
        config_file.stat().st_size,
    )
    return None
with open(config_file, encoding="utf-8") as f:
    data = json.load(f)
```

---

## Info

### IN-01: Unreachable `p90 is None` fallback branch

**File:** `core/threshold_manager.py:130-138`
**Issue:** The `if p90 is None:` guard at line 130 logs a warning and returns `status="calibrating"`. However, this branch is structurally unreachable: `P90Calculator.calculate_p90_limit()` returns `None` only when `blocks` is empty or falsy (line 83: `if not blocks: return None`), but `get_threshold()` only reaches this point after confirming `count >= COLD_START_MINIMUM` (10), which guarantees `completed` is non-empty. The dead branch creates misleading log noise if it were somehow triggered.

**Fix:** Replace with an assertion to make the invariant explicit, or remove the branch:
```python
# Belt-and-suspenders: if this fires, it's a programming error upstream
assert p90 is not None, (
    f"P90Calculator returned None with {count} completed sessions — "
    "this indicates a logic error in get_threshold()"
)
```
If you prefer not to assert in production code, convert the log level to `error` and raise `RuntimeError` instead of silently returning a misleading `calibrating` state.

---

### IN-02: Test import is fragile — no `conftest.py` sets up `sys.path`

**File:** `tests/test_threshold_manager.py:16`
**Issue:** The import `from core.threshold_manager import ThresholdState, get_threshold` works only when pytest is run from the project root (where `core/` is a top-level package). There is no `conftest.py` at the project root or in `tests/` to add the project root to `sys.path`. Running `pytest tests/` from inside the `tests/` directory, or running with a different working directory, will produce `ModuleNotFoundError`.

**Fix:** Add a `conftest.py` at the project root (or `tests/`) with:
```python
# conftest.py (project root)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```
Or configure `pythonpath` in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

---

### IN-03: Redundant `kwargs.get("tokens_used", tokens_used)` lookups

**File:** `ui/session_display.py:288` and `ui/session_display.py:304`
**Issue:** In both the `auto` and `manual` threshold branches, the code reads:
```python
tokens_used_val = kwargs.get("tokens_used", tokens_used)
```
`tokens_used` is already a named positional parameter in scope. `kwargs.get("tokens_used", ...)` will always fall through to the default because `tokens_used` is consumed as a positional argument and is never in `**kwargs`. The variable `tokens_used_val` is always equal to `tokens_used`.

**Fix:** Remove the indirection:
```python
if tokens_used > threshold_state.threshold_tokens:
```

---

### IN-04: Missing test scenario — P90 result feeds `token_limit` override in orchestrator

**File:** `tests/test_threshold_manager.py` (entire file)
**Issue:** The test suite thoroughly covers `get_threshold()` in isolation, but there are no integration tests verifying that the orchestrator correctly overrides `token_limit` with `threshold_state.threshold_tokens` for the `auto` and `manual` cases (orchestrator.py lines 181-184). The calibrating path (falls back to `DEFAULT_TOKEN_LIMIT`) is also untested through the orchestrator. A test exercising `_fetch_and_process_data()` with a mocked `get_threshold` return value of each status would catch any regression in that wiring.

**Fix:** Add orchestrator-level integration tests in a new `tests/test_orchestrator_threshold.py`:
```python
def test_orchestrator_uses_threshold_tokens_for_auto(monkeypatch, ...):
    """When threshold_state.status == 'auto', token_limit in monitoring_data
    should equal threshold_state.threshold_tokens."""
    ...

def test_orchestrator_uses_default_limit_during_calibration(monkeypatch, ...):
    """When threshold_state.status == 'calibrating', token_limit should be
    DEFAULT_TOKEN_LIMIT."""
    ...
```

---

_Reviewed: 2026-05-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
