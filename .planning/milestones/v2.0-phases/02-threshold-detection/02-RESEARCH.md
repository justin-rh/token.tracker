# Phase 2: Threshold Detection - Research

**Researched:** 2026-05-08
**Domain:** Python threshold calculation, config file I/O, Rich dashboard row insertion
**Confidence:** HIGH — all findings verified directly from source files in the working repo

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** All completed (non-active, non-gap) blocks feed P90 and the cold-start counter. No rate-limit filter.
- **D-02:** Cold-start minimum is 10 sessions, hardcoded. Not configurable.
- **D-03:** Manual override stored in `~/.claude-monitor/config.json`, key `overage_threshold_tokens` (integer).
- **D-04:** If `overage_threshold_tokens` is present in config.json, skip P90 entirely.
- **D-05:** During cold start: `Token limit: Calibrating (N/10 sessions)` — N is count of completed blocks.
- **D-06:** INCLUDED/OVERAGE label suppressed entirely during calibration.
- **D-07:** After calibration: `Token limit: 88,000 tokens (P90)` (actual value, not literal 88,000).
- **D-08:** When manual override: `Token limit: 88,000 tokens (manual)` — P90 does not run.
- **D-09:** Status row: `Status: ✅ INCLUDED` or `Status: 🔴 OVERAGE`. Suppressed during calibration.
- **D-10:** Status row placed prominently for Phase 3 extension (pool spend alongside).

### Claude's Discretion
- Exact row label and formatting (Rich markup, emoji vs colored text).
- Whether config.json is read at startup only or polled each refresh cycle.
- Error handling if `overage_threshold_tokens` is malformed — log warning, fall back to P90.

### Deferred Ideas (OUT OF SCOPE)
- Session reset model detection (rolling 5-hour vs calendar-day).
- Configurable cold-start minimum.
- `--custom-limit-tokens` CLI as override path (existing flag kept for power users, no new wiring).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| THRS-01 | Tool infers daily included-token limit automatically via P90 | P90Calculator.calculate_p90_limit() already implemented; orchestrator._calculate_token_limit() is the injection point |
| THRS-02 | Cold-start guard shows "Calibrating (N/10 sessions)" until 10 sessions exist | Completed-block count extracted from blocks list; display line appended to session_display screen_buffer |
| THRS-03 | User can manually set threshold via config file to override P90 | Pattern: replicate LastUsedParams read/write; config.json in existing ~/.claude-monitor/ directory |
</phase_requirements>

---

## Summary

Phase 2 is a focused integration task. The core algorithm (P90) is already implemented and tested. The work is wiring it correctly: (1) add a cold-start guard before the P90 call, (2) read a new config.json for the manual override, (3) surface the threshold state and INCLUDED/OVERAGE row in the dashboard. No new statistical libraries are needed.

The key architectural risk is that `Plans.get_token_limit("custom", blocks)` — the current code path — passes all completed blocks to P90 with no cold-start guard. That guard must be added. The plan should add it in `orchestrator._calculate_token_limit()` or in a new `core/threshold_manager.py` module, not inside `P90Calculator` or `Plans` (which should remain general-purpose).

A second subtlety: `totalTokens` in the serialized block dict counts only `input_tokens + output_tokens`, not cache tokens (see `_create_base_block_dict` in `data/analysis.py` line 194). This is what P90Calculator receives — it is working correctly as-is, but the planner should document this explicitly to avoid confusion.

**Primary recommendation:** Add `core/threshold_manager.py` as the authoritative module for threshold state. It encapsulates config.json read, cold-start count, and P90 call. Orchestrator calls it and stores the result in `monitoring_data`. Display controller reads it and renders the two new rows.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| P90 calculation | Core (p90_calculator.py) | — | Pure computation; no I/O dependencies |
| Cold-start counting | Core (threshold_manager.py) | — | Counts completed blocks from already-fetched data |
| Config.json read/write | Core (threshold_manager.py) | — | Mirrors LastUsedParams pattern in settings.py |
| Threshold state packaging | Orchestrator (orchestrator.py) | — | Orchestrator owns monitoring_data dict assembly |
| Dashboard row rendering | UI (session_display.py) | display_controller.py | Session display builds the screen_buffer list |

---

## Standard Stack

### Core (already installed — no new packages)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `statistics` (stdlib) | Python 3.12 built-in | `quantiles()` for P90 | Already used in p90_calculator.py |
| `json` (stdlib) | Python 3.12 built-in | config.json read/write | Already used in settings.py LastUsedParams |
| `pathlib.Path` (stdlib) | Python 3.12 built-in | ~/.claude-monitor/ path | Path.home() confirmed working on this machine |
| `rich` | Already installed | Dashboard row markup | Existing screen_buffer pattern |

No new dependencies. Phase 2 is pure stdlib + existing project code.

**Verified:** `Path.home() / ".claude-monitor"` resolves to `C:\Users\justin.rhoda\.claude-monitor` and the directory already exists with `last_used.json` inside it. [VERIFIED: bash probe on live system]

---

## Architecture Patterns

### System Architecture Diagram

```
Historical JSONL files
        |
        v
data/analysis.py:analyze_usage()
        |
        v
List[Dict] blocks  (keys: isActive, isGap, totalTokens, startTime, ...)
        |
        +---> [filter: not isActive, not isGap] ---> completed_blocks
        |                                                    |
        |                                           count_completed = len(completed_blocks)
        |                                                    |
        |                           +-------------------------+------------------------+
        |                           |                         |                        |
        |                  [count < 10]              [count >= 10]            [config.json present]
        |                  CALIBRATING              call P90Calculator        use manual override
        |                  state                   .calculate_p90_limit()    directly
        |                           |                         |                        |
        |                           +----------ThresholdState-+------------------------+
        |                                     (state, threshold_tokens, source, count)
        |
        v
monitoring/orchestrator.py:_calculate_token_limit()
   --> now returns ThresholdState (not just int)
        |
        v
monitoring_data dict
   {"data": ..., "token_limit": int, "threshold_state": ThresholdState, "args": ...}
        |
        v
ui/display_controller.py:create_data_display()
   --> extracts threshold_state
   --> passes to session_display
        |
        v
ui/session_display.py:format_active_session_screen()
   --> appends TWO new lines to screen_buffer:
       Line A: Token limit row (Calibrating / P90 value / manual value)
       Line B: Status row (INCLUDED / OVERAGE) — suppressed during CALIBRATING
```

### Recommended Project Structure

```
core/
├── threshold_manager.py    # NEW — ThresholdState dataclass + get_threshold() function
├── p90_calculator.py       # UNCHANGED — pure P90 math
├── plans.py                # UNCHANGED — plan enum and limits
├── settings.py             # UNCHANGED — Settings and LastUsedParams

monitoring/
├── orchestrator.py         # MODIFY — _calculate_token_limit() uses ThresholdManager

ui/
├── session_display.py      # MODIFY — add two new screen_buffer lines
├── display_controller.py   # MODIFY — pass threshold_state through to session_display

~/.claude-monitor/
├── last_used.json          # EXISTING — transient CLI params
└── config.json             # NEW — persistent manual override
```

### Pattern 1: ThresholdState Dataclass

**What:** A frozen dataclass that holds the complete threshold result from one evaluation cycle.

**When to use:** Returned by `get_threshold()` in `threshold_manager.py`; stored in `monitoring_data["threshold_state"]`.

```python
# Source: [VERIFIED: derived from existing P90Calculator and Plans patterns in this repo]
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass(frozen=True)
class ThresholdState:
    status: Literal["calibrating", "auto", "manual"]
    threshold_tokens: Optional[int]   # None when calibrating
    completed_session_count: int      # always populated (for display N/10)
    cold_start_minimum: int = 10      # hardcoded per D-02
```

### Pattern 2: config.json Read — Mirrors LastUsedParams

**What:** `~/.claude-monitor/config.json` contains `{ "overage_threshold_tokens": 88000 }`. Read at startup (or each refresh — implementer's discretion per Claude's Discretion).

**When to use:** At the top of `get_threshold()` before cold-start count or P90 call.

```python
# Source: [VERIFIED: mirrors core/settings.py LastUsedParams.load() at lines 55-71]
import json
import logging
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".claude-monitor"
CONFIG_FILE = CONFIG_DIR / "config.json"

logger = logging.getLogger(__name__)

def _read_manual_override() -> Optional[int]:
    """Read overage_threshold_tokens from config.json, or None if absent/invalid."""
    if not CONFIG_FILE.exists():
        return None
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        value = data.get("overage_threshold_tokens")
        if isinstance(value, int) and value > 0:
            return value
        if value is not None:
            logger.warning(
                f"config.json: overage_threshold_tokens={value!r} is not a positive int — "
                "falling back to P90"
            )
    except Exception as e:
        logger.warning(f"Failed to read config.json: {e}")
    return None
```

**Write pattern** (atomic, same as LastUsedParams.save()):

```python
# Source: [VERIFIED: core/settings.py LastUsedParams.save() lines 29-53]
def write_manual_override(tokens: int) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"overage_threshold_tokens": tokens}
    temp = CONFIG_FILE.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    temp.replace(CONFIG_FILE)
```

The `.tmp` + `replace()` approach prevents partial writes (same pattern used by `LastUsedParams.save()`).

### Pattern 3: Completed Block Count for Cold-Start

**What:** Count blocks where `isGap=False` AND `isActive=False`. This is the D-01 definition of "completed sessions."

**Critical detail:** The blocks list passed to orchestrator is the serialized dict format from `data/analysis.py:_create_base_block_dict()`. The keys are camelCase (`isActive`, `isGap`, `totalTokens`) — same format P90Calculator already expects.

```python
# Source: [VERIFIED: data/analysis.py lines 177-203 — _create_base_block_dict()]
def _count_completed_sessions(blocks: list) -> int:
    """Count non-active, non-gap session blocks per D-01."""
    return sum(
        1 for b in blocks
        if not b.get("isGap", False) and not b.get("isActive", False)
        and b.get("totalTokens", 0) > 0   # exclude empty blocks
    )
```

**Note on totalTokens:** In the serialized dict, `totalTokens = input_tokens + output_tokens` only (cache tokens are in `tokenCounts` separately). This is an existing P90Calculator assumption that is already correct — do not change it.

### Pattern 4: Dashboard Row Insertion

**What:** Two new lines appended to `screen_buffer` in `format_active_session_screen()`.

**Where:** In `ui/session_display.py`, insert after the separator that follows the Burn Rate / Cost Rate block (before the Predictions section). The Predictions section starts at the `screen_buffer.append("")` then `"🔮 [value]Predictions:[/]"` lines (~line 311-312).

**Exact existing context before insertion point:**
```python
# Source: [VERIFIED: ui/session_display.py lines 254-266]
screen_buffer.append(
    f"🔥 [value]Burn Rate:[/]              [warning]{burn_rate:.1f}[/] [dim]tokens/min[/] {velocity_emoji}"
)
cost_per_min_display = CostIndicator.render(cost_per_min)
screen_buffer.append(
    f"💲 [value]Cost Rate:[/]              {cost_per_min_display} [dim]$/min[/]"
)
# <-- INSERT HERE: separator + Token limit row + Status row
screen_buffer.append("")
screen_buffer.append("🔮 [value]Predictions:[/]")
```

**New rows to add:**

```python
# Source: [VERIFIED: mirrors existing Rich markup style in session_display.py]
# Insert after Cost Rate, before blank line preceding Predictions section

screen_buffer.append(f"[separator]{'─' * 60}[/]")

# Token limit row — three states per D-05 / D-07 / D-08
if threshold_state.status == "calibrating":
    screen_buffer.append(
        f"🎯 [value]Token limit:[/]          "
        f"[dim]Calibrating ({threshold_state.completed_session_count}/10 sessions)[/]"
    )
elif threshold_state.status == "auto":
    screen_buffer.append(
        f"🎯 [value]Token limit:[/]          "
        f"[info]{threshold_state.threshold_tokens:,} tokens[/] [dim](P90)[/]"
    )
else:  # manual
    screen_buffer.append(
        f"🎯 [value]Token limit:[/]          "
        f"[info]{threshold_state.threshold_tokens:,} tokens[/] [dim](manual)[/]"
    )

# Status row — per D-09: suppressed during calibration
if threshold_state.status != "calibrating" and threshold_state.threshold_tokens:
    is_over = tokens_used > threshold_state.threshold_tokens
    if is_over:
        screen_buffer.append("🔴 [error]Status:[/]               [error]OVERAGE[/]")
    else:
        screen_buffer.append("✅ [success]Status:[/]              [success]INCLUDED[/]")
```

### Anti-Patterns to Avoid

- **Adding cold-start logic inside P90Calculator:** The calculator is a pure math module. Cold-start is a policy decision that belongs in `threshold_manager.py` or the orchestrator.
- **Adding cold-start logic inside `Plans.get_token_limit()`:** That method is general-purpose and used across plans. Adding cold-start there would break non-custom plan paths.
- **Reading config.json inside the display layer:** I/O should not happen in UI code. Read in threshold_manager, pass the result through `monitoring_data`.
- **Storing `ThresholdState` in `Settings`:** Settings is a Pydantic BaseSettings wired to CLI args. Computed state does not belong there.
- **Using `statistics.quantiles()` with n < 2:** The existing P90Calculator guards against empty blocks with `if not hits: return cfg.default_min_limit`. The cold-start guard (10 sessions) fires before P90 is called, so this guard becomes a belt-and-suspenders backup. Do not remove it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| P90 calculation | Custom percentile math | `P90Calculator.calculate_p90_limit()` | Already implemented, tested, cached |
| Atomic file write | Own temp-file logic | `.tmp` + `Path.replace()` pattern from `LastUsedParams.save()` | Prevents partial writes on Windows |
| Rich markup rendering | String formatting | Existing `[value]`, `[dim]`, `[info]`, `[success]`, `[error]`, `[separator]` tags | Style tokens already defined in themes.py |
| Block dict key names | Guessing / reimplementing | Use `isActive`, `isGap`, `totalTokens` from `_create_base_block_dict()` | These are the exact keys P90Calculator expects |

---

## Key Integration Points — Verified Signatures

### `P90Calculator.calculate_p90_limit()`

```python
# Source: [VERIFIED: core/p90_calculator.py lines 79-97]
def calculate_p90_limit(
    self,
    blocks: Optional[List[Dict[str, Any]]] = None,
    use_cache: bool = True,
) -> Optional[int]:
```

- Input: list of dicts with keys `isGap` (bool), `isActive` (bool), `totalTokens` (int)
- Returns: `Optional[int]` — returns `None` if blocks is empty or falsy
- Has built-in 1-hour LRU cache keyed on `(time_bucket, blocks_tuple)`
- Already falls back to all completed blocks when no rate-limit-hit sessions exist (lines 42-44)
- **No cold-start guard exists.** With 1 completed block, returns a value. Phase 2 must guard externally.

### `Plans.get_token_limit("custom", blocks)`

```python
# Source: [VERIFIED: core/plans.py lines 122-142]
@classmethod
def get_token_limit(cls, plan: str, blocks: Optional[List[Dict[str, Any]]] = None) -> int:
```

- For `plan == "custom"` with blocks: calls `P90Calculator().calculate_p90_limit(blocks)`
- If P90 returns `None`: falls back to `cfg.token_limit` (44,000 for custom plan — see `PLAN_LIMITS`)
- **No cold-start guard exists here either.** With 1 block it returns a P90 value (likely wrong).
- Phase 2 should bypass this method for threshold detection and call P90Calculator directly via `threshold_manager.py`, after the cold-start check passes.

### `orchestrator._calculate_token_limit()`

```python
# Source: [VERIFIED: monitoring/orchestrator.py lines 212-233]
def _calculate_token_limit(self, data: Dict[str, Any]) -> int:
    if not self._args:
        return DEFAULT_TOKEN_LIMIT
    plan: str = getattr(self._args, "plan", "pro")
    try:
        if plan == "custom":
            blocks: List[Any] = data.get("blocks", [])
            return get_token_limit(plan, blocks)
        return get_token_limit(plan)
    except Exception as e:
        logger.exception(f"Error calculating token limit: {e}")
        return DEFAULT_TOKEN_LIMIT
```

- Currently returns a bare `int`. Phase 2 must change this return type to include `ThresholdState`.
- Two options: (A) return `ThresholdState` from this method and update the caller in `_fetch_and_process_data()`, or (B) compute `ThresholdState` separately and add it to `monitoring_data` alongside `token_limit`. Option B is less disruptive to existing code that already consumes `monitoring_data["token_limit"]`.

### `monitoring_data` dict structure

```python
# Source: [VERIFIED: monitoring/orchestrator.py lines 173-179]
monitoring_data = {
    "data": data,
    "token_limit": token_limit,      # int — keep unchanged for backward compat
    "args": self._args,
    "session_id": self.session_monitor.current_session_id,
    "session_count": self.session_monitor.session_count,
}
# Phase 2 adds:
monitoring_data["threshold_state"] = threshold_state   # ThresholdState
```

### `display_controller.create_data_display()` — threshold_state pass-through

```python
# Source: [VERIFIED: ui/display_controller.py lines 201-319]
def create_data_display(self, data, args, token_limit) -> RenderableType:
```

- Signature must be extended to accept `threshold_state: Optional[ThresholdState] = None`
- Currently passes `**processed_data` to `format_active_session_screen()`. Add `threshold_state` to `processed_data` dict.

### `session_display.format_active_session_screen()` — existing signature

```python
# Source: [VERIFIED: ui/session_display.py lines 131-154]
def format_active_session_screen(
    self,
    plan: str, timezone: str, tokens_used: int, token_limit: int,
    usage_percentage: float, tokens_left: int, ...
    **kwargs,
) -> list[str]:
```

- Has `**kwargs` — `threshold_state` can be passed without breaking the signature.
- The `custom` plan branch (lines 188-266) is where new rows should be inserted.
- The non-custom branch (lines 268-309) does not need the new rows in Phase 2 (company plan is "custom").

---

## Common Pitfalls

### Pitfall 1: Passing SessionBlock Objects to P90Calculator Instead of Dicts

**What goes wrong:** `P90Calculator.calculate_p90_limit()` expects `List[Dict]` with camelCase keys. `data["blocks"]` from `monitoring_data` is the serialized dict list (correct). If code passes raw `SessionBlock` objects (which use `is_active`, `is_gap`, `total_tokens`), the calculator silently sees all values as falsy defaults and returns `cfg.default_min_limit`.

**Why it happens:** `data/analyzer.py` works with `SessionBlock` objects. `data/analysis.py:_create_result()` converts them to dicts. The orchestrator receives the dict form. The risk is a developer tracing back to `SessionBlock` and passing the wrong object type.

**How to avoid:** In `threshold_manager.get_threshold(blocks)`, assert that blocks is a list of dicts and that the first element has an `isGap` key, not `is_gap`. Add a guard:
```python
if blocks and hasattr(blocks[0], 'is_gap'):
    raise TypeError("threshold_manager expects serialized dict blocks, not SessionBlock objects")
```

**Warning signs:** P90 always returns 19,000 (the `DEFAULT_TOKEN_LIMIT`) regardless of session history.

### Pitfall 2: Cold-Start Counts All Blocks Instead of Only Completed

**What goes wrong:** Counting blocks including active and gap blocks inflates the count. A fresh install with 9 completed sessions + 1 active session would show `count=10` and P90 would activate, but only 9 data points are valid. Similarly, gap blocks should not count.

**How to avoid:** Filter: `not isGap and not isActive and totalTokens > 0`. The `totalTokens > 0` guard also excludes empty blocks that represent no real usage.

### Pitfall 3: config.json Malformed Value Treated as Zero

**What goes wrong:** `overage_threshold_tokens: 0` (user typo) is valid JSON but would set the threshold to zero, making every session appear as OVERAGE. The read function must validate `isinstance(value, int) and value > 0`.

**How to avoid:** In `_read_manual_override()`, validate `value > 0` explicitly and log a warning if it fails. Return `None` to fall back to P90 rather than propagating the bad value.

### Pitfall 4: Atomic Write Race on Windows

**What goes wrong:** Writing config.json directly (not via temp file) risks a partial write if the process is killed between the `open()` and `close()` calls. On Windows, a partial JSON file will fail to parse on next startup.

**How to avoid:** Use `.tmp` + `Path.replace()` — exactly as `LastUsedParams.save()` does. This is atomic on Windows (NTFS guarantees that `rename()` on the same volume is atomic).

### Pitfall 5: token_limit Backward Compatibility Break

**What goes wrong:** `monitoring_data["token_limit"]` is currently an `int`. If Phase 2 changes this to `ThresholdState`, any code reading the existing int field will crash.

**How to avoid:** Add a parallel key `monitoring_data["threshold_state"]` without removing or changing `monitoring_data["token_limit"]`. During calibration, set `token_limit` to a sensible fallback (e.g., `DEFAULT_TOKEN_LIMIT` from plans.py) so the existing progress bar and percentage calculations do not divide by zero or render garbage.

---

## State Transition Diagram

```
                  startup
                     |
        +------------+-----------+
        |                        |
  config.json                config.json
  has valid                  absent or
  overage_threshold_tokens   no valid value
        |                        |
        v                        v
   MANUAL state         count completed blocks
   (D-04: skip P90)             |
        |             +---------+---------+
        |             |                   |
        |        count < 10          count >= 10
        |        CALIBRATING         AUTO state
        |        state               (P90 runs)
        |             |                   |
        +-------------+-------------------+
                      |
                 ThresholdState returned
                 (status, threshold_tokens, count)
```

---

## Code Examples

### Minimal get_threshold() implementation

```python
# Source: [VERIFIED: derived from p90_calculator.py and plans.py patterns in this repo]
# File: core/threshold_manager.py

COLD_START_MINIMUM = 10  # D-02: hardcoded

def get_threshold(blocks: list) -> ThresholdState:
    """
    Evaluate threshold from block history and config.json.

    Args:
        blocks: Serialized block dicts (isActive, isGap, totalTokens keys)

    Returns:
        ThresholdState with status in {"calibrating", "auto", "manual"}
    """
    # D-04: check config.json first; if present, skip P90 entirely
    manual = _read_manual_override()
    if manual is not None:
        return ThresholdState(
            status="manual",
            threshold_tokens=manual,
            completed_session_count=_count_completed_sessions(blocks),
        )

    # D-01: count completed (non-active, non-gap) blocks for cold-start
    count = _count_completed_sessions(blocks)

    # D-02: cold-start guard
    if count < COLD_START_MINIMUM:
        return ThresholdState(
            status="calibrating",
            threshold_tokens=None,
            completed_session_count=count,
        )

    # D-01: all completed blocks feed P90
    completed = [
        b for b in blocks
        if not b.get("isGap", False) and not b.get("isActive", False)
        and b.get("totalTokens", 0) > 0
    ]
    from claude_monitor.core.p90_calculator import P90Calculator
    p90 = P90Calculator().calculate_p90_limit(completed)
    if p90 is None:
        # Should not happen after cold-start guard, but be defensive
        return ThresholdState(status="calibrating", threshold_tokens=None, completed_session_count=count)

    return ThresholdState(status="auto", threshold_tokens=p90, completed_session_count=count)
```

### Orchestrator change (minimal)

```python
# Source: [VERIFIED: monitoring/orchestrator.py _fetch_and_process_data() lines 139-203]
# Change in _fetch_and_process_data() — add two lines after token_limit calculation:

from claude_monitor.core.threshold_manager import get_threshold

# existing:
token_limit: int = self._calculate_token_limit(data)

# new:
blocks = data.get("blocks", [])
threshold_state = get_threshold(blocks)

monitoring_data = {
    "data": data,
    "token_limit": token_limit,           # keep existing — no breakage
    "threshold_state": threshold_state,   # new
    "args": self._args,
    "session_id": self.session_monitor.current_session_id,
    "session_count": self.session_monitor.session_count,
}
```

---

## Environment Availability

Step 2.6: SKIPPED — Phase 2 is pure Python stdlib changes with no new external tools, services, CLIs, or databases. The `~/.claude-monitor/` directory already exists on this machine. [VERIFIED: bash probe]

---

## Open Questions

1. **config.json read frequency**
   - What we know: `last_used.json` is read once at startup in `Settings.load_with_last_used()`.
   - What's unclear: Should config.json be re-read each refresh cycle to pick up live edits without restart?
   - Recommendation: Read at startup only (simpler). If the user edits config.json, they can restart. Note this in user docs. This is Claude's discretion per CONTEXT.md.

2. **token_limit backward compat during calibration**
   - What we know: `monitoring_data["token_limit"]` is used by `display_controller._calculate_token_limits()` and the progress bar percentage.
   - What's unclear: What int should `token_limit` be set to during calibration so the existing bar renders sensibly?
   - Recommendation: Set `token_limit = DEFAULT_TOKEN_LIMIT` (19,000) during calibration. The bar will show a percentage, but since the Status row is suppressed (D-09) and the Token limit row shows "Calibrating", the bar value is not meaningful. Alternatively, set to a large number (e.g., 999,999) so usage always shows as a small percentage during calibration. This is Claude's discretion.

3. **format_active_session_screen — custom vs non-custom branch**
   - What we know: The `custom` plan branch (lines 188-266) is the relevant path. The non-custom branch uses a different layout.
   - What's unclear: Should the Token limit / Status rows appear in the non-custom branch too?
   - Recommendation: Insert only in the `custom` plan branch for Phase 2. Non-custom plans have static limits and don't use P90. Phase 3 can re-evaluate.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | config.json read at startup only is the right default | Open Questions | Low — user can restart; explicit in docs |
| A2 | `totalTokens` excluding cache tokens is the correct unit for P90 | Architecture Patterns | Low — P90Calculator already works on this assumption; consistent with existing behavior |
| A3 | Token limit row should only appear in the `custom` plan branch | Open Questions | Low — non-custom plans use static limits; no user-visible regression |

All code signatures, block dict key names, file paths, and existing patterns are VERIFIED from source.

---

## Sources

### Primary (HIGH confidence — verified from source files)

- `core/p90_calculator.py` — `calculate_p90_limit()` signature, cache behavior, fallback logic (lines 79-97)
- `core/plans.py` — `Plans.get_token_limit("custom", blocks)` path (lines 122-142); `DEFAULT_TOKEN_LIMIT = 19_000` (line 84)
- `core/settings.py` — `LastUsedParams.save()` / `.load()` atomic write pattern (lines 19-84); `~/.claude-monitor/` directory (line 24)
- `monitoring/orchestrator.py` — `_calculate_token_limit()` entry point (lines 212-233); `monitoring_data` dict structure (lines 173-179)
- `data/analysis.py` — `_create_base_block_dict()` serialized key names (lines 177-203); `totalTokens` = input+output only (line 194)
- `core/models.py` — `SessionBlock` dataclass (lines 72-110); no `session_id` field confirmed
- `ui/session_display.py` — Rich markup patterns, `screen_buffer` list structure (lines 183-334); `custom` plan branch (lines 188-266); insertion point (lines 254-266)
- `ui/display_controller.py` — `create_data_display()` signature (line 201); `_process_active_session_data()` return dict (lines 388-410)
- `bash probe` — `Path.home() / ".claude-monitor"` resolves to `C:\Users\justin.rhoda\.claude-monitor` and directory exists

### Secondary (MEDIUM confidence)

- `.planning/research/ARCHITECTURE.md` — overall component map and integration philosophy
- `.planning/research/PITFALLS.md` — Windows-specific concerns for config file I/O

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; stdlib only
- Architecture: HIGH — all integration points read directly from source
- Pitfalls: HIGH — verified from source (not just design docs)
- Block dict key names: HIGH — verified from `data/analysis.py:_create_base_block_dict()`

**Research date:** 2026-05-08
**Valid until:** 2026-06-08 (stable codebase; no fast-moving external dependencies)
