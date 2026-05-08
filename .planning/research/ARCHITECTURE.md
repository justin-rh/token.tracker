# Architecture Research: Overage Layer on Claude Monitor Fork

**Researched:** 2026-05-07
**Overall Confidence:** MEDIUM-HIGH (core codebase verified via GitHub source; overage layer is net-new design)

---

## Component Boundaries

The reference tool has a clean layered architecture. Data flows in one direction with no circular dependencies.

```
[JSONL files on disk]
        |
        v
data/reader.py          — discovers *.jsonl via Path.rglob(), parses into UsageEntry objects
        |
        v
data/analyzer.py        — groups entries into SessionBlock objects (5-hour windows),
                          detects limit-hit messages, flags isGap / isActive
        |
        v
core/p90_calculator.py  — consumes blocks list, returns int (token threshold)
core/calculations.py    — consumes blocks + active block, returns BurnRate + UsageProjection
core/pricing.py         — stateless: (tokens, model) -> cost_usd
core/plans.py           — plan enum + PLAN_LIMITS dict + helper accessors
core/settings.py        — Pydantic BaseSettings, holds plan type + custom_limit_tokens
        |
        v
monitoring/data_manager.py   — 30-second TTL cache around analyze_usage()
monitoring/session_monitor.py — session change detection, fires callbacks
monitoring/orchestrator.py   — background thread refresh loop, notifies registered callbacks
        |
        v
ui/display_controller.py     — receives monitoring_data dict, calls progress bars / components
ui/components.py             — VelocityIndicator, CostIndicator, AdvancedCustomLimitDisplay
ui/progress_bars.py          — TokenProgressBar, TimeProgressBar, ModelUsageBar
ui/layouts.py                — assembles panels into Rich Group
ui/session_display.py        — session summary table
ui/table_views.py            — daily/monthly table views
```

Key facts confirmed from source:

- `reader.py` uses `Path(data_path).expanduser()` — tilde expansion is the single path assumption
- `analyzer.py` `SessionBlock` carries `total_tokens`, `cost_usd`, `is_active`, `is_gap`, `start_time`, `end_time`
- `p90_calculator.py` input is `List[Dict]` with keys `isGap`, `isActive`, `totalTokens` — returns `int` (the P90 threshold in tokens)
- `orchestrator.py` wraps everything into a `monitoring_data` dict and calls registered callbacks
- `display_controller.py` receives `monitoring_data` dict + `token_limit` int, does all threshold comparisons itself

---

## Overage Layer Integration Point

**Add one new module: `core/overage.py`**

Do not subclass or decorate existing classes. The reference tool's display path already does threshold comparison inside `display_controller.py` using a passed-in `token_limit`. The cleanest extension is:

1. `core/overage.py` — pure calculation module, no UI dependencies
2. `core/settings.py` — extend `Settings` with two new fields
3. `monitoring/orchestrator.py` — compute `OverageState` alongside existing metrics; include it in `monitoring_data` dict
4. `ui/display_controller.py` — render one new panel from `OverageState`

This approach requires touching four files, all of which are well-bounded. No existing classes need to be subclassed or monkey-patched.

### Why not subclass?

`Settings` (Pydantic BaseSettings), `P90Calculator`, and `SessionBlock` are dataclasses or simple classes with no intended extension points. Adding fields to Settings via a subclass creates two separate config objects — the rest of the codebase imports `Settings` directly, so a subclass would require patching every import. Direct field extension is cleaner.

### Why not a decorator?

The calculation pipeline is procedural (function calls, not class method calls), so a decorator does not compose well here. The overage state depends on the P90 result which is already computed in the orchestrator loop — there is no single "wrap this call" point.

### The right pattern: parallel computation in the orchestrator

```
orchestrator._fetch_and_process_data():
    data = data_manager.get_data()         # existing
    token_limit = p90_calculator.calculate_p90_limit(blocks)   # existing
    overage_state = compute_overage(active_block, token_limit, settings)  # NEW
    monitoring_data["overage"] = overage_state   # NEW key in existing dict
    notify_callbacks(monitoring_data)
```

`compute_overage()` lives in `core/overage.py` and is a pure function — easy to unit test in isolation.

---

## Data Model for Overage

```python
# core/overage.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class OverageState:
    # Threshold
    included_threshold_tokens: int      # P90 result (or manual override)
    threshold_source: str               # "p90" | "manual"

    # Current period usage
    tokens_used: int                    # active block total_tokens
    cost_used_usd: float                # active block cost_usd

    # Overage calculation
    is_over: bool                       # tokens_used > included_threshold_tokens
    overage_tokens: int                 # max(0, tokens_used - included_threshold_tokens)
    overage_cost_usd: float             # cost of overage tokens at blended rate

    # Pool tracking
    pool_size_usd: float                # from settings (default 500.00)
    pool_spent_usd: float               # cumulative across current period
    pool_remaining_usd: float           # pool_size_usd - pool_spent_usd
    pool_pct_remaining: float           # 0.0 - 100.0

    # Burn projection
    overage_burn_rate_usd_per_hr: float # cost_per_hour when in overage
    pool_exhaustion_hrs: Optional[float] # None if burn rate = 0
```

### Period definition

Use the **active SessionBlock's window** (`start_time` to `end_time`, default 5 hours) as the overage period. This aligns with how the reference tool already segments time — no new period concept is needed.

For pool tracking across multiple blocks (cumulative daily spend), sum `overage_cost_usd` across all non-gap, non-active blocks in the current calendar day, then add the active block's overage. This gives a "total pool spent today" figure without requiring a new persistence layer.

The setting `reset_hour` (already in Settings, `Optional[int]`) controls the daily boundary — reuse it for overage period rollover.

---

## Threshold Detection Architecture

### How P90 feeds into overage detection

The P90 calculator already returns a clean `int` (token count). The orchestrator already calls it to get `token_limit`. No changes to `P90Calculator` are needed.

The overage layer consumes the same value:

```
P90Calculator.calculate_p90_limit(blocks) -> int (e.g. 88_000)
                    |
                    v
compute_overage(active_block.total_tokens, p90_limit, settings)
                    |
                    v
OverageState.is_over = (total_tokens > p90_limit)
OverageState.overage_tokens = max(0, total_tokens - p90_limit)
```

### Overage cost calculation

The reference tool's `pricing.py` already calculates `cost_usd` per UsageEntry by model. The `SessionBlock.cost_usd` field is the sum of all entry costs in the block.

To attribute cost specifically to overage tokens, use a blended rate derived from the active block:

```python
if active_block.total_tokens > 0:
    blended_rate = active_block.cost_usd / active_block.total_tokens  # $ per token
else:
    blended_rate = 0.0

overage_cost = overage_tokens * blended_rate
```

This is an approximation — it assumes the token mix (input/output/cache) is uniform across the included and overage portions. Given that the included threshold is high (tens of thousands of tokens) and the blended rate is stable within a session, this approximation is accurate enough for a monitoring dashboard. Confidence: MEDIUM.

An exact calculation would require splitting UsageEntry records at the threshold crossing point, which requires per-entry token cumsum tracking and significantly more complexity. Defer to a later phase if precision is required.

### Manual threshold override

Add `overage_threshold_tokens: Optional[int]` to Settings. If set, skip P90 and use this value directly. This handles the case where Anthropic discloses the exact included limit.

```python
# In compute_overage():
if settings.overage_threshold_tokens is not None:
    threshold = settings.overage_threshold_tokens
    source = "manual"
else:
    threshold = p90_limit  # from P90Calculator
    source = "p90"
```

---

## Windows Path Fix Location

**Single fix location: `data/reader.py`**

The reference tool's path construction:

```python
data_path = Path(data_path if data_path else "~/.claude/projects").expanduser()
```

`Path.expanduser()` on Windows resolves `~` to `USERPROFILE` (e.g. `C:\Users\justin.rhoda`), so `Path("~/.claude/projects").expanduser()` correctly produces `C:\Users\justin.rhoda\.claude\projects` on Windows without any change.

However, the `rglob("*.jsonl")` call that follows is also correct — Python's pathlib handles backslash/forward-slash uniformly on Windows.

The one real risk is the `LastUsedParams` persistence path in `core/settings.py`:

```python
~/.claude-monitor/last_used.json
```

This also uses `expanduser()` and will resolve correctly on Windows.

**Action required:** Verify empirically on Windows that `Path("~/.claude/projects").expanduser().exists()` returns True with actual Claude Code logs present. If it fails (e.g. HOME env var not set), fall back to:

```python
Path.home() / ".claude" / "projects"
```

`Path.home()` uses `USERPROFILE` directly and does not depend on the `HOME` env variable — it is the more robust fallback on Windows.

**Recommendation:** Replace the `expanduser()` default in `reader.py` with `Path.home() / ".claude" / "projects"` to eliminate the `HOME` vs `USERPROFILE` ambiguity entirely. This is a one-line change at the default argument.

---

## Suggested Build Order

Dependencies flow from data in to UI out. Follow the same order.

### Phase 1 — Windows path fix + smoke test (no new features)
1. Fork the repo
2. `data/reader.py`: change default path to `Path.home() / ".claude" / "projects"`
3. Run the existing tool against live Windows JSONL logs
4. Confirm sessions load, P90 calculates, Rich UI renders in Windows Terminal

This phase validates the base before any overage logic is added. If the existing tool does not run on Windows, diagnose before proceeding.

### Phase 2 — Settings extension
1. `core/settings.py`: add `overage_pool_size_usd: float = 500.0` and `overage_threshold_tokens: Optional[int] = None`
2. Extend `LastUsedParams` persistence if these settings should survive restarts

### Phase 3 — Overage calculation module
1. `core/overage.py`: implement `OverageState` dataclass and `compute_overage()` pure function
2. Unit tests for `compute_overage()` — test: included, at-threshold, over-threshold, empty-block, zero-burn cases
3. No UI changes in this phase — verify the math in isolation

### Phase 4 — Orchestrator integration
1. `monitoring/orchestrator.py`: call `compute_overage()` inside `_fetch_and_process_data()`, attach result to `monitoring_data["overage"]`
2. `monitoring/data_manager.py`: no change needed — it caches the raw data; orchestrator processes it

### Phase 5 — UI panel
1. `ui/display_controller.py`: extract `overage_state` from `monitoring_data`, pass to new render function
2. `ui/components.py` or new `ui/overage_panel.py`: `OveragePanel` renders included/overage indicator, pool % bar, $/hr burn rate, exhaustion projection
3. `ui/layouts.py`: insert overage panel into the layout group

### Phase 6 — Hardening
1. Edge cases: P90 returns None (insufficient history) — show "threshold: calculating..." state
2. Overage burn rate = 0 — suppress exhaustion projection
3. Pool fully spent — show "POOL EXHAUSTED" alert
4. Integration test: run against a session that crosses the threshold mid-session

---

## Confidence Levels

| Finding | Confidence | Basis |
|---------|------------|-------|
| `reader.py` uses `Path.expanduser()` for the default path | HIGH | Read source code directly from GitHub |
| `Path("~/.claude/projects").expanduser()` works on Windows | HIGH | Python docs + CPython issue tracker confirm USERPROFILE resolution |
| `Path.home()` is more robust than `expanduser()` on Windows | HIGH | CPython issue #80445 documents the HOME vs USERPROFILE ambiguity |
| P90 calculator returns `int` (token count), input is `List[Dict]` | HIGH | Read full source verbatim from GitHub |
| `SessionBlock` fields (`total_tokens`, `cost_usd`, `is_active`) | HIGH | Read models.py from GitHub |
| `monitoring_data` dict is the integration point in orchestrator | HIGH | Read orchestrator.py from GitHub |
| Blended rate approximation for overage cost | MEDIUM | Derived from pricing.py logic; approximation accuracy depends on session token mix consistency |
| Calendar-day cumulative pool tracking via existing `reset_hour` | MEDIUM | Settings field confirmed; rollover logic is net-new design |
| New pricing (Opus 4 = $5/$25, Sonnet 4.6 = $3/$15 per 1M tokens) | MEDIUM | Multiple web sources agree; not in official Anthropic docs directly |
| 5-hour session window as overage period unit | HIGH | Confirmed from analyzer.py; aligns with Claude Code's reset model |
| `display_controller.py` is the correct UI integration point | HIGH | Read source; it is the only place that assembles Rich panels from monitoring data |

---

## Open Questions

1. **Exact included token limit**: The P90 approach infers it. If Anthropic discloses the actual limit for the company plan, plug it into `overage_threshold_tokens` and P90 becomes irrelevant. Worth asking the account owner.

2. **Pool accumulation period**: Is the $500 pool monthly, weekly, or per-billing-cycle? The architecture above uses calendar-day to match the tool's existing `reset_hour` concept. If the pool resets monthly, the cumulative sum logic needs a longer window. This changes Phase 6 hardening significantly.

3. **Whether `cost_usd` in SessionBlock includes cache costs**: From pricing.py, it does — all four token types (input, output, cache_creation, cache_read) are included. The blended rate calculation is therefore inclusive of cache costs. Confirm this holds for company plan billing.

4. **Rich rendering on Windows Terminal**: The reference tool targets Unix terminals. Rich is cross-platform and Windows Terminal supports VT100 sequences, but emoji rendering (the progress bar uses 🔴/🟡/🟢) may need fallback characters in older ConHost windows. Test in Phase 1.
