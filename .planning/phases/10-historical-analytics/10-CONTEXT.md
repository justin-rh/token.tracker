---
phase: 10-historical-analytics
type: context
---

# Phase 10: Historical Analytics — Context

## Goal

Render a daily pool-spend bar chart inline in the terminal dashboard, covering the current billing cycle.

## Requirements

- **ANLX-01**: Bar chart of daily pool spend for the current billing cycle appears inline in the terminal
- **ANLX-02**: Each bar is labeled with date and spend amount; current day is visually distinct
- **ANLX-03**: Chart is hidden entirely when no pool spend data exists for the billing cycle

## Architecture

### Data flow

```
compute_pool_state()                   → PoolState.daily_pool_spend
    (pool_state_manager.py)                (tuple of (date_str, spend_usd))
        ↓
monitoring_data["pool_state"]          (orchestrator passes pool_state unchanged)
        ↓
format_active_session_screen()         → _render_daily_spend_chart()
    (session_display.py)                   inserted after burn rate row
```

### D-01: `daily_pool_spend` field on PoolState

Type: `tuple` — immutable, compatible with frozen dataclass. Each element is `(date_str: str, spend_usd: float)` in ascending date order, covering every calendar day from `billing_cycle_start` to today (inclusive), with `0.0` for days with no overage spend.

Field has a default of `()` so that existing `PoolState(...)` call sites that don't supply it remain valid (backwards compatible during the migration).

### D-02: Population in compute_pool_state()

During the existing block loop, accumulate a `dict[str, float]` keyed by ISO date (`"YYYY-MM-DD"`) using `datetime.fromisoformat(block["startTime"]).date().isoformat()`. Only accumulate for blocks that pass the existing `all_sessions or _classify_overage(...)` check (same condition as `pool_spend_usd`).

After the loop, build the full range: iterate `cycle_start` to `today` one day at a time using `timedelta(days=1)`, pulling from the dict (defaulting to `0.0`). Convert to `tuple`.

### D-03: Chart rendering

Bar width = 20 chars. Each bar is scaled to `max_spend` across all days.
- Filled: `█` — Rich style `[value]` (cyan) for past days, `[success]` (green) for today
- Empty: `░` — `[dim]` style

Format per row:
```
   MMM DD  [filled_bar][empty_bar]  est. $X.XX
```
Today's row gets `[success]` color on the bar and a `◀ today` suffix.

### D-04: Chart visibility condition

Show the chart panel only when `pool_state.daily_pool_spend` contains at least one entry with `spend_usd > 0`. This satisfies ANLX-03 without needing a separate flag.

Insertion point in `format_active_session_screen()`: immediately after the burn-rate row block (line ~314), before the per-project breakdown separator.

### D-05: No persistence changes

`pool_spend.json` cache is not extended — `daily_pool_spend` is recomputed from blocks on every call (consistent with D-03 from phase 3 context: "pool_spend.json is a cache only"). This keeps the cache format stable.
