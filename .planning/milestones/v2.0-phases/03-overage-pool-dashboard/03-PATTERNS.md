# Phase 3: Overage Pool Dashboard - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 7
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/pool_state_manager.py` | service | CRUD | `core/threshold_manager.py` | exact |
| `~/.claude-monitor/pool_spend.json` | config (runtime state) | file-I/O | `core/settings.py:LastUsedParams.save()` | exact |
| `~/.claude-monitor/config.json` (extend) | config | file-I/O | `core/threshold_manager.py:_read_manual_override()` | exact |
| `monitoring/orchestrator.py` (modify) | service | request-response | existing `threshold_state` block, lines 173–196 | exact |
| `ui/display_controller.py` (modify) | controller | request-response | `processed_data["threshold_state"] = threshold_state`, line 281 | exact |
| `ui/session_display.py` (modify) | component | request-response | Phase 2 threshold rows, lines 269–312 | exact |
| `cli/main.py` (modify) | controller | request-response | `threshold_state=monitoring_data.get("threshold_state")` call, line 195 | exact |

---

## Pattern Assignments

---

### `core/pool_state_manager.py` (service, CRUD)

**Analog:** `core/threshold_manager.py`

**Imports pattern** (`core/threshold_manager.py` lines 1–9):
```python
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path.home() / ".claude-monitor"
```

**Dataclass pattern** (`core/threshold_manager.py` lines 16–23):
```python
@dataclass(frozen=True)
class ThresholdState:
    """Result of one threshold evaluation cycle."""

    status: Literal["calibrating", "auto", "manual"]
    threshold_tokens: Optional[int]    # None when calibrating
    completed_session_count: int
    cold_start_minimum: int = 10
```
Copy this structure exactly for `PoolState`. Replace fields with:
```python
@dataclass(frozen=True)
class PoolState:
    """Result of one pool spend evaluation cycle."""
    pool_size_usd: float
    pool_spend_usd: float
    pool_remaining_usd: float
    pool_pct_spent: float
    billing_cycle_start: str       # ISO date string "YYYY-MM-DD"
    is_overage: bool
```

**Config-read pattern** (`core/threshold_manager.py` lines 26–50):
```python
def _read_manual_override(config_dir: Path) -> Optional[int]:
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return None
    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        value = data.get("overage_threshold_tokens")
        if isinstance(value, int) and value > 0:
            return value
        if value is not None:
            logger.warning(
                "config.json: overage_threshold_tokens=%r is not a positive int "
                "— falling back to P90",
                value,
            )
    except Exception as exc:
        logger.warning("Failed to read config.json: %s", exc)
    return None
```
For pool config, adapt to read two keys (`pool_size_usd`, `billing_cycle_start_day`) with their own validation rules (D-07: `billing_cycle_start_day` must be int 1–28; `pool_size_usd` must be positive float).

**Factory function signature** (`core/threshold_manager.py` lines 69–88):
```python
def get_threshold(blocks: list, config_dir: Optional[Path] = None) -> ThresholdState:
    if config_dir is None:
        config_dir = _DEFAULT_CONFIG_DIR
    ...
```
Mirror this signature for the pool factory:
```python
def compute_pool_state(
    blocks: list,
    threshold_state,          # ThresholdState — for OVERAGE classification
    config_dir: Optional[Path] = None,
) -> PoolState:
    if config_dir is None:
        config_dir = _DEFAULT_CONFIG_DIR
    ...
```

**Error handling pattern** — all reads wrapped in `try/except Exception as exc: logger.warning(...)` and return a safe default (None or zero-filled state). Never let config read errors crash the monitoring loop.

---

### `~/.claude-monitor/pool_spend.json` (runtime state file, file-I/O)

**Analog:** `core/settings.py:LastUsedParams.save()` lines 27–53

**Atomic write pattern** (`core/settings.py` lines 27–53):
```python
def save(self, settings: "Settings") -> None:
    try:
        params = {
            "theme": settings.theme,
            "timezone": settings.timezone,
            # ... other fields ...
            "timestamp": datetime.now().isoformat(),
        }

        self.config_dir.mkdir(parents=True, exist_ok=True)

        temp_file = self.params_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(params, f, indent=2)
        temp_file.replace(self.params_file)

        logger.debug(f"Saved last used params to {self.params_file}")

    except Exception as e:
        logger.warning(f"Failed to save last used params: {e}")
```
Apply this pattern verbatim for `_write_pool_spend_cache()`. Fields to write:
```python
payload = {
    "pool_spend_usd": pool_state.pool_spend_usd,
    "billing_cycle_start": pool_state.billing_cycle_start,
    "last_updated": datetime.now().isoformat(),
}
final_path = config_dir / "pool_spend.json"
temp_file = final_path.with_suffix(".tmp")
```

**Load pattern** (`core/settings.py` lines 55–71):
```python
def load(self) -> Dict[str, Any]:
    if not self.params_file.exists():
        return {}
    try:
        with open(self.params_file) as f:
            params = json.load(f)
        ...
        return params
    except Exception as e:
        logger.warning(f"Failed to load last used params: {e}")
        return {}
```
Mirror for `_read_pool_spend_cache()`: return `{}` (not raise) on any failure so the caller falls back to recomputing from logs.

---

### `~/.claude-monitor/config.json` — new keys (config, file-I/O)

**Analog:** `core/threshold_manager.py:_read_manual_override()` lines 26–50 (the full pattern for optional config key with type validation and warning-on-bad-value).

**Keys to add:**
```json
{
  "pool_size_usd": 500.0,
  "billing_cycle_start_day": 1
}
```
Both keys are optional. Existing keys (`overage_threshold_tokens`) are untouched — a single `json.load()` call reads all keys.

**Validation rules to implement in `_read_pool_config()`:**
- `pool_size_usd`: `isinstance(raw, (int, float)) and raw > 0` — else log warning, default 500.0
- `billing_cycle_start_day`: `isinstance(raw, int) and 1 <= raw <= 28` — else log warning, default 1

Copy warning message format from analog:
```python
logger.warning(
    "config.json: pool_size_usd=%r is not a positive number — using default 500.0",
    raw_size,
)
```

---

### `monitoring/orchestrator.py` (modify — add pool state computation)

**Analog:** The existing Phase 2 threshold block, `monitoring/orchestrator.py` lines 173–196

**Exact existing block to extend** (lines 173–196):
```python
# Phase 2: compute threshold state (cold-start / P90 auto / manual override)
# Only runs for custom plan; other plans have static limits with no P90 calibration.
blocks: List[Any] = data.get("blocks", [])
if getattr(self._args, "plan", "pro") == "custom":
    threshold_state: ThresholdState = get_threshold(blocks)
    # D-pitfall-5: keep token_limit as int for backward compat with progress bar math.
    # During calibration, use DEFAULT_TOKEN_LIMIT so percentage calculations don't
    # divide by zero or show misleading values. For auto/manual, use the real threshold.
    if threshold_state.status == "calibrating":
        token_limit = DEFAULT_TOKEN_LIMIT
    elif threshold_state.threshold_tokens is not None:
        token_limit = threshold_state.threshold_tokens
else:
    threshold_state = None

# Prepare monitoring data
monitoring_data: Dict[str, Any] = {
    "data": data,
    "token_limit": token_limit,
    "threshold_state": threshold_state,   # Phase 2
    "args": self._args,
    "session_id": self.session_monitor.current_session_id,
    "session_count": self.session_monitor.session_count,
}
```

**How to extend — insert after `threshold_state` line, before `monitoring_data` dict:**
```python
# Phase 3: compute pool state
from claude_monitor.core.pool_state_manager import compute_pool_state
pool_state = compute_pool_state(blocks, threshold_state)
```

**Add to `monitoring_data` dict** — one line added after `"threshold_state"`:
```python
"threshold_state": threshold_state,   # Phase 2
"pool_state": pool_state,             # Phase 3 NEW
```

**Import to add at top of file** (mirror existing threshold_manager import, line 9):
```python
from claude_monitor.core.threshold_manager import ThresholdState, get_threshold
# add below it:
from claude_monitor.core.pool_state_manager import PoolState, compute_pool_state
```

---

### `ui/display_controller.py` (modify — pass pool_state through)

**Analog:** `create_data_display()` Phase 2 pattern, lines 202–281

**Exact existing signature** (lines 202–208):
```python
def create_data_display(
    self,
    data: Dict[str, Any],
    args: Any,
    token_limit: int,
    threshold_state: Optional[ThresholdState] = None,  # new in Phase 2
) -> RenderableType:
```
Add `pool_state` as a new optional kwarg in the same position:
```python
def create_data_display(
    self,
    data: Dict[str, Any],
    args: Any,
    token_limit: int,
    threshold_state: Optional[ThresholdState] = None,
    pool_state: Optional["PoolState"] = None,          # Phase 3 NEW
) -> RenderableType:
```

**Exact existing passthrough line** (line 281):
```python
# Phase 2: pass threshold_state through to session_display via kwargs
processed_data["threshold_state"] = threshold_state
```
Add one line immediately below it:
```python
# Phase 3: pass pool_state through to session_display via kwargs
processed_data["pool_state"] = pool_state
```

**Import to add at top** (mirror existing ThresholdState import, line 21):
```python
from claude_monitor.core.threshold_manager import ThresholdState
# add below it:
from claude_monitor.core.pool_state_manager import PoolState
```

---

### `ui/session_display.py` (modify — add pool dashboard rows)

**Analog:** Phase 2 threshold rows, `ui/session_display.py` lines 269–312

**Exact end of Phase 2 block** (lines 269–312, last few lines):
```python
            # Phase 2: Threshold Detection rows (D-05, D-06, D-07, D-08, D-09)
            threshold_state = kwargs.get("threshold_state")
            if threshold_state is not None:
                screen_buffer.append(f"[separator]{'─' * 60}[/]")

                if threshold_state.status == "calibrating":
                    screen_buffer.append(
                        f"🎯 [value]Token limit:[/]          "
                        f"[dim]Calibrating ({threshold_state.completed_session_count}/10 sessions)[/]"
                    )
                    # D-06: INCLUDED/OVERAGE row suppressed entirely during calibration
                elif threshold_state.status == "auto":
                    ...
                    if tokens_used_val > threshold_state.threshold_tokens:
                        screen_buffer.append(
                            "🔴 [error]Status:[/]               [error]OVERAGE[/]"
                        )
                    else:
                        screen_buffer.append(
                            "✅ [success]Status:[/]              [success]INCLUDED[/]"
                        )
                else:  # manual
                    ...
                    if tokens_used_val > threshold_state.threshold_tokens:
                        screen_buffer.append(
                            "🔴 [error]Status:[/]               [error]OVERAGE[/]"
                        )
                    else:
                        screen_buffer.append(
                            "✅ [success]Status:[/]              [success]INCLUDED[/]"
                        )
```

**How to extend — add AFTER line 312** (inside the same `if threshold_state is not None` block, after INCLUDED/OVERAGE row is appended for auto/manual):
```python
            # Phase 3: Pool dashboard rows
            pool_state = kwargs.get("pool_state")
            if (
                pool_state is not None
                and threshold_state is not None
                and threshold_state.status != "calibrating"
            ):
                screen_buffer.append(f"[separator]{'─' * 60}[/]")

                # Pool spend row (always shown when threshold known)
                screen_buffer.append(
                    f"🏦 [value]Pool spent:[/]   est. ${pool_state.pool_spend_usd:.2f} / ${pool_state.pool_size_usd:.2f}"
                )

                # Progress bar — pass pool_pct_SPENT (not remaining) so color escalates correctly
                pool_bar = self._render_wide_progress_bar(pool_state.pool_pct_spent)
                pct_remaining = 100.0 - pool_state.pool_pct_spent
                screen_buffer.append(
                    f"   {pool_bar} {pct_remaining:.1f}% remaining"
                )

                # Burn rate + exhaustion — OVERAGE state only
                if pool_state.is_overage:
                    burn_rate_per_hr = (
                        (session_cost / max(1, elapsed_session_minutes)) * 60
                        if elapsed_session_minutes > 0
                        else 0.0
                    )
                    if burn_rate_per_hr > 0:
                        remaining_hrs = pool_state.pool_remaining_usd / burn_rate_per_hr
                        hours = int(remaining_hrs)
                        mins = int((remaining_hrs - hours) * 60)
                        exhaust_str = f"~{hours}h {mins}m remaining"
                    else:
                        exhaust_str = "—"
                    screen_buffer.append(
                        f"🔥 [value]Pool burn:[/]    est. ${burn_rate_per_hr:.2f}/hr — {exhaust_str}"
                    )
```

**`_render_wide_progress_bar` color thresholds** (lines 75–80) — critical to understand before using for pool:
```python
if percentage < 50:
    color = "🟢"
elif percentage < 80:
    color = "🟡"
else:
    color = "🔴"
```
Pass `pool_pct_spent` (spend %), NOT remaining %. As spend grows: green (<50% spent) → yellow (<80% spent) → red (>=80% spent). This matches D-14 (green when >50% remaining).

---

### `cli/main.py` (modify — pass pool_state to display_controller)

**Analog:** `cli/main.py` lines 191–196 — the existing `on_data_update` callback call

**Exact existing call** (lines 191–196):
```python
renderable = display_controller.create_data_display(
    data,
    args,
    monitoring_data.get("token_limit", token_limit),
    threshold_state=monitoring_data.get("threshold_state"),
)
```
Add one kwarg after `threshold_state`:
```python
renderable = display_controller.create_data_display(
    data,
    args,
    monitoring_data.get("token_limit", token_limit),
    threshold_state=monitoring_data.get("threshold_state"),
    pool_state=monitoring_data.get("pool_state"),          # Phase 3 NEW
)
```
No other changes to `cli/main.py`.

---

## Shared Patterns

### Atomic File Write
**Source:** `core/settings.py:LastUsedParams.save()` lines 43–53
**Apply to:** `core/pool_state_manager.py:_write_pool_spend_cache()`
```python
self.config_dir.mkdir(parents=True, exist_ok=True)
temp_file = self.params_file.with_suffix(".tmp")
with open(temp_file, "w") as f:
    json.dump(params, f, indent=2)
temp_file.replace(self.params_file)
```

### Config Read with Warning-on-Bad-Value
**Source:** `core/threshold_manager.py:_read_manual_override()` lines 36–50
**Apply to:** `core/pool_state_manager.py:_read_pool_config()` for both new config keys
```python
config_file = config_dir / "config.json"
if not config_file.exists():
    return <defaults>
try:
    with open(config_file, encoding="utf-8") as f:
        data = json.load(f)
    value = data.get("<key>")
    if isinstance(value, <expected_type>) and <valid_condition>:
        <use it>
    elif value is not None:
        logger.warning("config.json: <key>=%r is not valid — using default", value)
except Exception as exc:
    logger.warning("Failed to read config.json: %s", exc)
```

### kwargs passthrough for display extensions
**Source:** `ui/display_controller.py` line 281 + `ui/session_display.py` line 270
**Apply to:** All new display state objects (pool_state follows identical 3-hop chain)
```python
# display_controller.py — one line per new state:
processed_data["pool_state"] = pool_state

# session_display.py — read via kwargs:
pool_state = kwargs.get("pool_state")
```

### Frozen dataclass result object
**Source:** `core/threshold_manager.py` lines 16–23
**Apply to:** `PoolState` in `core/pool_state_manager.py`
```python
@dataclass(frozen=True)
class PoolState:
    ...
```
Immutable — prevents accidental mutation by display layer.

### Test file structure
**Source:** `tests/test_threshold_manager.py`
**Apply to:** `tests/test_pool_state_manager.py`

Key patterns to replicate:
- `tmp_path` fixture for config_dir injection (avoid writing to real `~/.claude-monitor`)
- Helper function `make_block(active, gap, tokens)` returning camelCase dict
- `caplog.at_level(logging.WARNING, logger="core.pool_state_manager")` for warning assertions
- Test each decision branch independently: calibrating (no threshold), INCLUDED session, OVERAGE session
- Test frozen dataclass mutation raises exception
- Test malformed config key falls back to default with warning logged

---

## No Analog Found

All files have direct analogs. No entries.

---

## Key Warnings for Planner

1. **Progress bar color direction** — always pass `pool_pct_spent` (not remaining) to `_render_wide_progress_bar`. The bar colors green < 50%, yellow < 80%, red >= 80% of the value passed. Passing remaining percentage inverts the colors.

2. **`session_cost` and `elapsed_session_minutes` are positional params** in `format_active_session_screen` (lines 138, 146) — they are available directly in the pool rows block without going through kwargs.

3. **`totalTokens` is input + output only** — does NOT include cache tokens. This is the value compared against `threshold_tokens` for OVERAGE classification per `_create_base_block_dict()`.

4. **Calibration guard required** — `threshold_state.threshold_tokens` is `None` when `status == "calibrating"`. Guard `_classify_overage()` with `if threshold_tokens is None: return False` to avoid `TypeError`.

5. **`pool_state` should still be computed and passed** even when plan != "custom", but pool rows in `session_display.py` are only rendered inside the `if plan in ["custom", "pro", "max5", "max20"]` block (which already gates the threshold rows). No special plan-gating needed beyond what already exists.

---

## Metadata

**Analog search scope:** `core/`, `monitoring/`, `ui/`, `cli/`, `tests/`
**Files scanned:** 7 source files read directly
**Pattern extraction date:** 2026-05-08
