# Phase 3: Overage Pool Dashboard - Research

**Researched:** 2026-05-08
**Domain:** Python dashboard extension — pool accounting, config persistence, Rich UI rows
**Confidence:** HIGH (all key findings verified by reading source files directly)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Pool spend = sum of `cost.total_cost_usd` from `statusline.jsonl` for all sessions in the current billing period where `tokens_used > threshold_tokens` (OVERAGE sessions).
- **D-02:** Full session cost counted when session crosses threshold mid-run. Slight over-estimate, acceptable.
- **D-03:** Pool spend recomputed from `statusline.jsonl` on each startup/refresh. `pool_spend.json` is a startup cache and billing cycle anchor only.
- **D-04:** Write `~/.claude-monitor/pool_spend.json` with: `pool_spend_usd` (float), `billing_cycle_start` (ISO date string), `last_updated` (ISO timestamp).
- **D-05:** `billing_cycle_start_day` stored in `config.json`, NOT `pool_spend.json`.
- **D-06:** On startup, if `pool_spend.json` exists, use its `billing_cycle_start` to filter entries. Else derive from `config.json → billing_cycle_start_day` + today.
- **D-07:** Two new config.json keys: `pool_size_usd` (float, default 500.0), `billing_cycle_start_day` (int 1–28, default 1).
- **D-08:** These keys optional; defaults apply when absent. Same malformed-value pattern (log warning + use default).
- **D-09:** $/hr burn rate = `session_cost_usd / elapsed_session_minutes × 60`.
- **D-10:** Pool exhaustion = `(pool_size_usd - pool_spend_usd) / burn_rate_per_hr`. Render as "~4h 23m remaining".
- **D-11:** Burn rate and exhaustion rows shown ONLY while in OVERAGE state.
- **D-12:** Phase 2 INCLUDED/OVERAGE row stays. Phase 3 adds new section below it (new separator).
- **D-13:** All cost figures carry "est." prefix: e.g., "Pool spent: est. $12.34 / $500.00".
- **D-14:** Pool % remaining displayed as Rich progress bar (reuse `_render_wide_progress_bar`). Green > 50%, yellow > 20%, red ≤ 20%.

### Claude's Discretion
- Exact Rich markup and emoji choices for pool dashboard rows (consistent with existing style)
- Whether `pool_spend.json` written on every refresh or only on startup/shutdown
- Error handling if `statusline.jsonl` missing or empty (fall back to pool_spend_usd = 0.0)
- Whether to add `PoolStateManager` class or inline the logic

### Deferred Ideas (OUT OF SCOPE)
- Session reset model detection (rolling 5-hour vs calendar-day) — not needed for pool tracking
- Billing API integration (v2 BILL-01)
- Alert on pool threshold (v2 BILL-02)
- Historical pool spend chart (v2 ANLX-01)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OVGE-01 | Prominent INCLUDED/OVERAGE status indicator | Phase 2 threshold rows already render this; Phase 3 extends below it |
| OVGE-02 | Estimated dollars spent from pool this billing month | `read_statusline_costs()` returns `{session_key: cost_usd}`; billing period filter via `startTime` in block dict |
| OVGE-03 | Pool % remaining as visual progress bar | `_render_wide_progress_bar(percentage)` is directly reusable |
| OVGE-04 | $/hr burn rate + projected exhaustion time | `session_cost` and `elapsed_session_minutes` already in `processed_data`; OVERAGE state gate from threshold_state |
| OVGE-05 | Pool spend persists across terminal restarts | `pool_spend.json` written with atomic-write pattern from `LastUsedParams.save()` |
| OVGE-06 | Pool size and billing cycle start user-configurable | Two new optional keys in `~/.claude-monitor/config.json`; read via `_read_manual_override` pattern |
| DISP-02 | All cost figures prefixed "est." | Inline string formatting — no structural change required |
</phase_requirements>

---

## Summary

Phase 3 adds a pool dashboard section to the active-session display. The core work is three tasks: (1) a new `core/pool_state_manager.py` module that reads config.json for pool settings, reads `~/.claude/statusline.jsonl` to sum OVERAGE session costs in the current billing period, and returns a `PoolState` dataclass; (2) wiring the pool state computation into `monitoring/orchestrator.py` after the existing threshold state block; and (3) rendering new display rows at the bottom of the Phase 2 threshold section in `ui/session_display.py`.

The billing period filter relies on the `startTime` ISO timestamp string in each serialized block dict, which was confirmed present in `_create_base_block_dict()`. Each block with `totalTokens > threshold_tokens` (from `ThresholdState.threshold_tokens`) is classified OVERAGE; its `costUSD` value is summed for `pool_spend_usd`. The `costUSD` field in the serialized block is the post-statusline-resolution value — it reflects the accurate `cost.total_cost_usd` figure from statusline.jsonl, not the removed raw `costUSD` JSONL field.

The primary risk is the `_render_wide_progress_bar` color-threshold mismatch: the existing bar uses green < 50% fill, yellow < 80%, red >= 80% (fill percentage). For pool remaining, we need the INVERSE: green while > 50% remaining, yellow > 20%, red <= 20%. The percentage passed to the bar must be `pool_spend / pool_size × 100` (spend percentage), and the color thresholds map naturally: as spend grows, color escalates. Confirmed this is the correct direction.

**Primary recommendation:** Implement `core/pool_state_manager.py` as a class parallel to `ThresholdManager`; wire it into the orchestrator immediately after `get_threshold()`; inject `pool_state` into `monitoring_data` alongside `threshold_state`; render rows in `session_display.py` via `kwargs.get("pool_state")`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pool spend computation | Core (pure calculation) | — | Billing period filter + OVERAGE classification is business logic; no UI dependency |
| State persistence (pool_spend.json) | Core | — | File I/O follows same pattern as `LastUsedParams` in settings.py |
| Config key reading | Core | — | Re-use existing config.json read pattern from `threshold_manager.py:_read_manual_override()` |
| Orchestrator wiring | Monitoring | — | `_fetch_and_process_data()` is the established integration point for all state computation |
| Display rows | UI (session_display) | — | Phase 2 established the kwargs pattern for appending new sections |
| Burn rate calculation | UI (or Core) | — | Value already in `processed_data` as `session_cost` / `elapsed_session_minutes`; can be computed in display or passed in PoolState |

---

## Standard Stack

### Core — All Verified [VERIFIED: read source files directly]

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `dataclasses` (stdlib) | Python 3.12 | `PoolState` frozen dataclass | Matches `ThresholdState` pattern exactly |
| `pathlib.Path` (stdlib) | Python 3.12 | File path construction | Already used throughout the codebase |
| `json` (stdlib) | Python 3.12 | Config read + pool_spend.json write | Already used in `settings.py`, `threshold_manager.py` |
| `datetime` (stdlib) | Python 3.12 | Billing period date arithmetic | Already used in `calculations.py`, `display_controller.py` |
| `logging` (stdlib) | Python 3.12 | Warning log for malformed config | Already used in `threshold_manager.py` |

No new third-party dependencies required. Phase 3 is a pure Python stdlib + existing project code extension.

---

## Architecture Patterns

### System Architecture Diagram

```
statusline.jsonl                  config.json
  (session costs)               (pool_size_usd,
       |                    billing_cycle_start_day)
       |                              |
       v                              v
core/pool_state_manager.py  <---------+
  compute_pool_state(blocks, threshold_state)
    - derive billing_cycle_start date
    - filter statusline entries to billing period
    - classify each block as INCLUDED / OVERAGE
    - sum OVERAGE costUSD -> pool_spend_usd
    - write pool_spend.json (startup cache)
    - return PoolState dataclass
       |
       v
monitoring/orchestrator.py
  _fetch_and_process_data()
    threshold_state = get_threshold(blocks)   [existing]
    pool_state = compute_pool_state(          [NEW]
        blocks, threshold_state, config_dir)
    monitoring_data["pool_state"] = pool_state
       |
       v
cli/main.py
  on_data_update(monitoring_data)
    renderable = display_controller.create_data_display(
        ..., threshold_state=..., pool_state=...)   [NEW param]
       |
       v
ui/display_controller.py
  create_data_display(...)
    processed_data["pool_state"] = pool_state       [NEW key]
    -> session_display.format_active_session_screen(**processed_data)
       |
       v
ui/session_display.py
  format_active_session_screen(**kwargs)
    pool_state = kwargs.get("pool_state")           [NEW kwargs read]
    [after Phase 2 threshold rows, line ~312]
    [separator] + pool dashboard rows
```

### Recommended Project Structure

```
core/
├── pool_state_manager.py   # NEW: PoolState dataclass + compute_pool_state()
├── threshold_manager.py    # Existing — Phase 2
├── statusline_cost.py      # Existing — used by pool_state_manager
└── settings.py             # Existing — atomic write pattern to replicate

monitoring/
└── orchestrator.py         # Extend _fetch_and_process_data() to call pool_state

ui/
└── session_display.py      # Extend format_active_session_screen() with pool rows

~/.claude-monitor/
├── config.json             # Add pool_size_usd, billing_cycle_start_day keys
└── pool_spend.json         # NEW: startup cache file
```

### Pattern 1: PoolState Frozen Dataclass

Mirrors `ThresholdState` exactly. Immutable result prevents accidental mutation.

```python
# core/pool_state_manager.py
# Source: verified from core/threshold_manager.py ThresholdState pattern

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class PoolState:
    """Result of one pool spend evaluation cycle."""
    pool_size_usd: float           # from config.json (default 500.0)
    pool_spend_usd: float          # sum of OVERAGE session costs this billing period
    pool_remaining_usd: float      # pool_size_usd - pool_spend_usd
    pool_pct_spent: float          # (pool_spend_usd / pool_size_usd) * 100
    billing_cycle_start: str       # ISO date string (YYYY-MM-DD)
    is_overage: bool               # True when current session is OVERAGE
```

### Pattern 2: Config Key Reading

Copy the `_read_manual_override()` pattern from `threshold_manager.py`. Read the key, validate type, log warning + use default on bad value.

```python
# Source: verified from core/threshold_manager.py:_read_manual_override()

def _read_pool_config(config_dir: Path) -> tuple[float, int]:
    """Read pool_size_usd and billing_cycle_start_day from config.json.
    Returns (pool_size_usd, billing_cycle_start_day) with defaults on missing/invalid.
    """
    config_file = config_dir / "config.json"
    pool_size = 500.0
    cycle_day = 1
    if not config_file.exists():
        return pool_size, cycle_day
    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        raw_size = data.get("pool_size_usd")
        if isinstance(raw_size, (int, float)) and raw_size > 0:
            pool_size = float(raw_size)
        elif raw_size is not None:
            logger.warning("config.json: pool_size_usd=%r is not a positive number — using default 500.0", raw_size)
        raw_day = data.get("billing_cycle_start_day")
        if isinstance(raw_day, int) and 1 <= raw_day <= 28:
            cycle_day = raw_day
        elif raw_day is not None:
            logger.warning("config.json: billing_cycle_start_day=%r is not int 1–28 — using default 1", raw_day)
    except Exception as exc:
        logger.warning("Failed to read config.json for pool settings: %s", exc)
    return pool_size, cycle_day
```

### Pattern 3: Atomic File Write for pool_spend.json

Copy the `LastUsedParams.save()` atomic write pattern. Write to `.tmp`, rename to final path.

```python
# Source: verified from core/settings.py:LastUsedParams.save()

def _write_pool_spend_cache(config_dir: Path, pool_state: PoolState) -> None:
    """Write pool_spend.json atomically to ~/.claude-monitor/."""
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pool_spend_usd": pool_state.pool_spend_usd,
        "billing_cycle_start": pool_state.billing_cycle_start,
        "last_updated": datetime.now().isoformat(),
    }
    final_path = config_dir / "pool_spend.json"
    temp_file = final_path.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(final_path)
    except Exception as exc:
        logger.warning("Failed to write pool_spend.json: %s", exc)
```

### Pattern 4: Billing Period Filter

The `startTime` field in the serialized block dict is an ISO 8601 string (e.g. `"2026-05-08T11:03:17.797008"` — verified from `_create_base_block_dict()` which calls `block.start_time.isoformat()`). Parse it with `datetime.fromisoformat()` and compare against `billing_cycle_start` date.

```python
# Source: verified from data/analysis.py:_create_base_block_dict()

from datetime import date, datetime

def _derive_billing_cycle_start(cycle_day: int) -> date:
    """Derive the most recent billing cycle start date from today and cycle_day."""
    today = date.today()
    if today.day >= cycle_day:
        return today.replace(day=cycle_day)
    else:
        # Go back to previous month
        if today.month == 1:
            return today.replace(year=today.year - 1, month=12, day=cycle_day)
        else:
            return today.replace(month=today.month - 1, day=cycle_day)

def _in_billing_period(start_time_str: str, cycle_start: date) -> bool:
    """Return True if block's startTime falls within the current billing period."""
    try:
        block_date = datetime.fromisoformat(start_time_str).date()
        return block_date >= cycle_start
    except (ValueError, TypeError):
        return False
```

### Pattern 5: OVERAGE Classification per Block

A block is OVERAGE if `totalTokens > threshold_tokens`. During calibration (`threshold_state.status == "calibrating"`), `threshold_tokens` is `None` — no blocks can be classified as OVERAGE, so pool spend is $0.00.

```python
# Source: verified from data/analysis.py block dict keys and threshold_manager.py

def _classify_overage(block: dict, threshold_tokens: Optional[int]) -> bool:
    """Return True if block consumed more tokens than the included limit."""
    if threshold_tokens is None:
        return False   # calibrating — no threshold known, no OVERAGE
    return block.get("totalTokens", 0) > threshold_tokens
```

### Pattern 6: Orchestrator Integration (Phase 2 precedent)

[VERIFIED: read monitoring/orchestrator.py lines 173–196]

Slot pool state computation immediately after `get_threshold()`. Include it in `monitoring_data` dict with a new key. Downstream (cli/main.py → display_controller → session_display) follows the same pass-through chain as `threshold_state`.

```python
# monitoring/orchestrator.py _fetch_and_process_data() — after threshold_state block

# Phase 3: compute pool state
from claude_monitor.core.pool_state_manager import compute_pool_state
pool_state = compute_pool_state(blocks, threshold_state)

monitoring_data = {
    ...existing keys...,
    "threshold_state": threshold_state,   # Phase 2
    "pool_state": pool_state,             # Phase 3 NEW
}
```

### Pattern 7: Display Row Injection via kwargs

[VERIFIED: read ui/session_display.py lines 269–312 and ui/display_controller.py line 281]

`format_active_session_screen` already uses `**kwargs` for threshold_state injection. Phase 3 adds `pool_state` to `processed_data` dict in `display_controller.py` and reads it via `kwargs.get("pool_state")` in `session_display.py`.

Add to `display_controller.py:create_data_display()` after threshold_state line:
```python
processed_data["pool_state"] = pool_state  # from monitoring_data
```

Add to `session_display.py:format_active_session_screen()` after line 312 (end of Phase 2 block):
```python
pool_state = kwargs.get("pool_state")
if pool_state is not None and threshold_state is not None and threshold_state.status != "calibrating":
    screen_buffer.append(f"[separator]{'─' * 60}[/]")
    # Pool rows here (see Display Rows below)
```

### Pattern 8: Burn Rate in Display

[VERIFIED: read ui/session_display.py lines 259–263 and ui/display_controller.py line 60]

`session_cost` comes from `active_block.get("costUSD", 0.0)` which is the statusline-resolved value (confirmed in data/analysis.py). `elapsed_session_minutes` is computed in `display_controller.py:SessionCalculator.calculate_time_data()`. Both are already in `processed_data` when `format_active_session_screen` is called — no recalculation needed.

```python
# In session_display.py pool rows section (OVERAGE state only):
# session_cost and elapsed_session_minutes are positional params, not kwargs

burn_rate_per_hr = (session_cost / max(1, elapsed_session_minutes)) * 60 if elapsed_session_minutes > 0 else 0.0
if burn_rate_per_hr > 0:
    remaining_hrs = pool_state.pool_remaining_usd / burn_rate_per_hr
    hours = int(remaining_hrs)
    mins = int((remaining_hrs - hours) * 60)
    exhaust_str = f"~{hours}h {mins}m remaining"
else:
    exhaust_str = "—"
```

### Pattern 9: Display Row Format

Following the existing cost-row convention: `"[emoji] [value]Label:[/]   [markup]{value}[/]"`.

```python
# Pool spend row (always shown when pool_state is available + threshold known)
screen_buffer.append(
    f"🏦 [value]Pool spent:[/]   est. ${pool_state.pool_spend_usd:.2f} / ${pool_state.pool_size_usd:.2f}"
)

# Progress bar row
pool_bar = self._render_wide_progress_bar(pool_state.pool_pct_spent)
pct_remaining = 100.0 - pool_state.pool_pct_spent
screen_buffer.append(
    f"   {pool_bar} {pct_remaining:.1f}% remaining"
)

# Burn rate + exhaustion row (OVERAGE state only, burn_rate > 0)
if pool_state.is_overage:
    screen_buffer.append(
        f"🔥 [value]Pool burn:[/]    est. ${burn_rate_per_hr:.2f}/hr — {exhaust_str}"
    )
```

### Anti-Patterns to Avoid

- **Accumulating pool_spend in a running counter:** D-03 requires recomputing from logs on each refresh. A counter can drift from reality and is harder to test.
- **Putting billing period logic in display_controller.py:** Business logic belongs in `core/` (pure, testable). Display layer should only receive a pre-computed PoolState.
- **Reading statusline.jsonl in display_controller or session_display:** The UI layer has no file I/O. All reads happen in `core/pool_state_manager.py`.
- **Passing session_id to look up statusline costs:** `read_statusline_costs()` already resolves all costs keyed by session_id or timestamp. For pool accounting, iterate the serialized blocks (already have `costUSD` from statusline resolution in `data/analyzer.py`). Do NOT call `read_statusline_costs()` again — the block's `costUSD` field is already the statusline-sourced value.
- **Using `_render_wide_progress_bar` with pool_remaining_pct:** The bar's internal color uses green < 50%, yellow < 80%, red >= 80% (fill %). Pass `pool_pct_SPENT` (not remaining) so color escalates correctly as pool depletes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | Custom lock/write logic | `.tmp` + `Path.replace()` pattern (from `LastUsedParams.save()`) | Already proven, handles partial-write crashes |
| Progress bar rendering | Custom ASCII bar | `_render_wide_progress_bar(pct)` | Existing 50-char Rich bar with color logic, reuse directly |
| Config key validation | Custom validator | Mirror `_read_manual_override()` pattern | Consistent: log warning + default on bad value |
| Billing period start date | Complex calendar library | `date.today().replace(day=...)` with month rollback | stdlib datetime is sufficient for day-of-month arithmetic |
| ISO timestamp parsing | Custom regex | `datetime.fromisoformat()` | Python 3.12 stdlib handles ISO 8601 strings produced by `.isoformat()` |

---

## Common Pitfalls

### Pitfall 1: Progress Bar Color Direction

**What goes wrong:** Passing `pool_remaining_pct` (100 → 0 as pool depletes) to `_render_wide_progress_bar`. The bar shows green when pool is nearly empty.

**Why it happens:** Intuitive to pass "remaining" percentage to a progress bar. But the bar's color thresholds treat low values as "low usage" (green).

**How to avoid:** Always pass `pool_pct_SPENT = (pool_spend / pool_size) * 100`. As spend grows, color escalates: green (< 50% spent) → yellow (< 80% spent) → red (>= 80% spent). This matches D-14: green > 50% remaining = < 50% spent.

**Warning signs:** Pool at 90% depleted shows green bar.

### Pitfall 2: Burn Rate Division by Zero

**What goes wrong:** `pool_remaining_usd / burn_rate_per_hr` raises `ZeroDivisionError` or shows infinity when no active session is running.

**Why it happens:** `elapsed_session_minutes` can be 0 at session start, or `session_cost` is 0.0 before any API calls are made.

**How to avoid:** Guard: `if burn_rate_per_hr > 0` before computing exhaustion. When burn rate is 0, suppress the exhaustion string entirely (show "—" or omit the row).

**Warning signs:** Crash at dashboard startup, or "inf hours remaining" in display.

### Pitfall 3: Calibrating State Leaks into Pool Accounting

**What goes wrong:** `threshold_state.threshold_tokens` is `None` when calibrating. Calling `block.get("totalTokens", 0) > None` raises `TypeError`.

**Why it happens:** Not checking `threshold_state.status` before accessing `threshold_tokens`.

**How to avoid:** In `_classify_overage()`, return `False` when `threshold_tokens is None`. Pool spend will correctly show $0.00 during calibration. The display gate also suppresses pool rows during calibration.

**Warning signs:** `TypeError: '>' not supported between instances of 'int' and 'NoneType'` in orchestrator.

### Pitfall 4: pool_spend.json Billing Period Mismatch

**What goes wrong:** `pool_spend.json` exists with `billing_cycle_start` from a previous period. On startup, pool spend appears to include sessions from the old period.

**Why it happens:** D-06 says to use `pool_spend.json`'s `billing_cycle_start` on startup — but that start date needs to be validated against today. If today is after the next cycle start date, `pool_spend.json` is stale.

**How to avoid:** On load, compare `pool_spend.json`'s `billing_cycle_start` date against the current period's start derived from `billing_cycle_start_day` + today. If the cached start is earlier than the current cycle start, recompute (the cached file is from the previous period).

**Warning signs:** Pool spend shows "$X spent" on day 1 of a new billing cycle.

### Pitfall 5: session_cost Field Source

**What goes wrong:** `display_controller.py:_extract_session_data()` reads `active_block.get("costUSD", 0.0)`. For burn rate in the pool section, you use the same `session_cost` positional parameter — confirmed this is the statusline-resolved value. Do not attempt to re-read statusline.jsonl from session_display.py.

**Why it happens:** The field is named `costUSD` (the old removed field) but its value is now the statusline-sourced cost (set by `data/analyzer.py`). The name is misleading.

**How to avoid:** Trust the `session_cost` parameter passed to `format_active_session_screen`. It is statusline-sourced. Confirmed by tracing: analyzer.py sets `block.cost_usd = _resolve_block_cost(...)` → analysis.py serializes as `"costUSD": block.cost_usd` → display_controller reads `active_block.get("costUSD")`.

### Pitfall 6: Day-of-Month Edge Case (day > 28)

**What goes wrong:** `billing_cycle_start_day = 31` but February has only 28 days. `date.replace(day=31)` raises `ValueError`.

**Why it happens:** Config.json validation allows 1–28 per D-07, but if user manually edits config to a higher value, the date arithmetic crashes.

**How to avoid:** The config validation already caps at 28 (D-07). Still: wrap `_derive_billing_cycle_start()` in a try/except, log warning, fall back to day=1.

---

## Key API Signatures (Verified)

### read_statusline_costs() — NOT needed for pool accounting

[VERIFIED: read core/statusline_cost.py]

```python
def read_statusline_costs() -> dict:
    # Returns {session_id_or_timestamp_str: cost_usd_float}
    # Returns {} if file absent or unreadable
```

**Phase 3 does NOT call this directly.** The serialized block dicts from `data/analysis.py` already have `costUSD` set to the statusline-resolved value. Pool accounting reads `block["costUSD"]` from the blocks list already in `monitoring_data["data"]["blocks"]`.

### ThresholdState — complete field reference

[VERIFIED: read core/threshold_manager.py]

```python
@dataclass(frozen=True)
class ThresholdState:
    status: Literal["calibrating", "auto", "manual"]
    threshold_tokens: Optional[int]    # None when calibrating
    completed_session_count: int
    cold_start_minimum: int = 10
```

- Access: `threshold_state.threshold_tokens` — may be `None`
- Access: `threshold_state.status` — check for `"calibrating"` before using threshold_tokens

### Serialized Block Dict — complete field reference

[VERIFIED: read data/analysis.py:_create_base_block_dict()]

```python
{
    "id": str,
    "isActive": bool,
    "isGap": bool,
    "startTime": "2026-05-08T11:03:17.797008",  # datetime.isoformat(), no timezone offset
    "endTime": "2026-05-08T16:03:17.797000",
    "actualEndTime": str | None,
    "tokenCounts": {
        "inputTokens": int,
        "outputTokens": int,
        "cacheCreationInputTokens": int,
        "cacheReadInputTokens": int,
    },
    "totalTokens": int,  # input + output only (not cache)
    "costUSD": float,    # statusline-resolved cost; name is legacy
    "models": list[str],
    "perModelStats": dict,
    "sentMessagesCount": int,
    "durationMinutes": float,
    "entries": list[dict],
    "entries_count": int,
    # Optional (from _add_optional_block_data):
    "burnRate": {"tokensPerMinute": float, "costPerHour": float},
    "projection": dict,
    "limitMessages": list,
}
```

**CRITICAL:** `totalTokens` is `input_tokens + output_tokens` only (does NOT include cache tokens). This is the value compared against `threshold_tokens` to classify OVERAGE. Confirmed from `_create_base_block_dict()` line 194–195.

### format_active_session_screen — signature summary

[VERIFIED: read ui/session_display.py lines 131–154]

```python
def format_active_session_screen(
    self,
    plan: str,
    timezone: str,
    tokens_used: int,           # positional — available directly
    token_limit: int,
    usage_percentage: float,
    tokens_left: int,
    elapsed_session_minutes: float,  # positional — use for burn rate
    total_session_minutes: float,
    burn_rate: float,
    session_cost: float,         # positional — use for burn rate
    per_model_stats: dict,
    sent_messages: int,
    entries: list[dict],
    predicted_end_str: str,
    reset_time_str: str,
    current_time_str: str,
    show_switch_notification: bool = False,
    show_exceed_notification: bool = False,
    show_tokens_will_run_out: bool = False,
    original_limit: int = 0,
    **kwargs,                    # threshold_state, pool_state live here
) -> list[str]:
```

`session_cost` and `elapsed_session_minutes` are positional parameters already present when pool rows are rendered. Use them directly — no need to pass through kwargs.

### _render_wide_progress_bar — signature

[VERIFIED: read ui/session_display.py lines 64–95]

```python
def _render_wide_progress_bar(self, percentage: float) -> str:
    # percentage: 0–100+ (capped at 100 for fill, color from raw value)
    # Color: < 50 -> green emoji, < 80 -> yellow emoji, >= 80 -> red emoji
    # Returns: "{emoji} [{rich_markup_bar}]"
```

### create_data_display — signature

[VERIFIED: read ui/display_controller.py lines 202–208]

```python
def create_data_display(
    self,
    data: Dict[str, Any],
    args: Any,
    token_limit: int,
    threshold_state: Optional[ThresholdState] = None,
) -> RenderableType:
```

Phase 3 adds `pool_state` as a new optional kwarg, OR adds it to `processed_data` dict before calling `format_active_session_screen`. The latter approach (no signature change to `create_data_display`) is simpler and consistent with Phase 2 pattern.

### on_data_update in cli/main.py — callback

[VERIFIED: read cli/main.py lines 175–196]

```python
renderable = display_controller.create_data_display(
    data,
    args,
    monitoring_data.get("token_limit", token_limit),
    threshold_state=monitoring_data.get("threshold_state"),
)
```

Phase 3 adds `pool_state=monitoring_data.get("pool_state")` to this call after adding it to `create_data_display`'s signature.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Read `costUSD` from session JSONL | Read `cost.total_cost_usd` from statusline.jsonl | Upstream v1.0.9 | `costUSD` in JSONL is removed; must use statusline |
| Direct block attribute access | Serialized camelCase dict access | Phase 1–2 | `block["costUSD"]` not `block.cost_usd`; `block["totalTokens"]` not `block.total_tokens` |
| Single threshold comparison | `ThresholdState` with status flow | Phase 2 | Calibrating state must suppress pool accounting |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `startTime` in serialized block dict is naive ISO string (no timezone offset) — `datetime.fromisoformat()` parses it directly | Billing Period Filter | If timezone offset is present, fromisoformat() still works in Python 3.12; low risk |
| A2 | `totalTokens` comparison against `threshold_tokens` correctly classifies OVERAGE (not cache-inclusive) | OVERAGE Classification | If threshold was calibrated with cache tokens included, classification boundary shifts slightly |

---

## Open Questions

1. **Should pool_spend.json be written on every refresh or only startup/shutdown?**
   - What we know: D-03 says the file is a "startup cache" — implies write-on-startup is sufficient.
   - What's unclear: If the tool crashes mid-session, last refresh's spend is lost until next restart.
   - Recommendation: Write on every orchestrator cycle (every `update_interval` seconds). The atomic write is fast and the file is tiny. Claude's discretion per CONTEXT.md.

2. **Where should burn rate for pool exhaustion be computed — PoolState or session_display?**
   - What we know: `session_cost` and `elapsed_session_minutes` are positional params already available in `format_active_session_screen`. Computing burn rate there requires no new plumbing.
   - What's unclear: If `PoolState` carries `burn_rate_usd_per_hr`, it becomes testable in isolation.
   - Recommendation: Compute `burn_rate_per_hr` and `pool_exhaust_hrs` inside the display method using the positional params — simpler, no data flow change needed. Keep PoolState as a pure pool-spend record.

3. **pool_spend.json stale detection — is the check needed in Phase 3?**
   - What we know: D-06 says on startup use `pool_spend.json`'s `billing_cycle_start`. Pitfall 4 above documents the stale-detection need.
   - Recommendation: Include stale detection in the initial implementation. The check is two lines: compare cached start against derived current cycle start; recompute if stale.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — Phase 3 is pure Python stdlib + existing project modules)

---

## Sources

### Primary (HIGH confidence — all findings verified by direct source read)

- `core/statusline_cost.py` — `read_statusline_costs()` return type, key format, error handling
- `core/threshold_manager.py` — `ThresholdState` fields, `get_threshold()` contract
- `core/settings.py` — `LastUsedParams.save()` atomic write pattern, config_dir location
- `core/calculations.py` — `BurnRateCalculator.calculate_burn_rate()` for elapsed-time handling reference
- `core/models.py` — `SessionBlock` field names (snake_case on object)
- `data/analysis.py` — `_create_base_block_dict()` — complete serialized block dict schema
- `data/analyzer.py` — `_resolve_block_cost()` — confirms `block.cost_usd` is statusline-sourced
- `monitoring/orchestrator.py` — `_fetch_and_process_data()` integration point, `monitoring_data` dict structure
- `ui/display_controller.py` — `create_data_display()` signature, `processed_data` dict construction, callback chain
- `ui/session_display.py:131–154` — `format_active_session_screen()` full signature with `**kwargs`
- `ui/session_display.py:64–95` — `_render_wide_progress_bar()` color thresholds
- `ui/session_display.py:269–312` — Phase 2 threshold rows (Phase 3 appends immediately after line 312)
- `cli/main.py:175–196` — `on_data_update` callback showing how `threshold_state` is extracted and passed
- `tests/test_threshold_manager.py` — test patterns to replicate for `pool_state_manager` tests
- `.planning/phases/03-overage-pool-dashboard/03-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- `.planning/research/ARCHITECTURE.md` — component boundaries, confirmed align with current source
- `~/.claude-monitor/last_used.json` — confirmed ISO timestamp format used in practice

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all stdlib; no new dependencies
- Architecture: HIGH — verified every integration point from source
- Pitfalls: HIGH — identified from actual code paths, not speculation
- API signatures: HIGH — read verbatim from source files

**Research date:** 2026-05-08
**Valid until:** 2026-06-08 (stable codebase, no upstream churn expected)
