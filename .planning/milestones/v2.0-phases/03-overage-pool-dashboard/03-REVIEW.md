---
phase: 03-overage-pool-dashboard
reviewed: 2026-05-08T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - core/pool_state_manager.py
  - tests/test_pool_state_manager.py
  - monitoring/orchestrator.py
  - ui/display_controller.py
  - cli/main.py
  - ui/session_display.py
findings:
  critical: 0
  high: 2
  medium: 3
  low: 2
  info: 3
  total: 10
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed six files covering the Phase 3 overage pool dashboard: the new `core/pool_state_manager.py` module (PoolState dataclass + compute_pool_state()), its 14-test suite, the orchestrator integration, and three UI integration points.

The architectural approach is sound and mirrors the established threshold_manager.py pattern well. The atomic write for pool_spend.json is correctly implemented. The billing cycle derivation logic, calibration guard, and "est." prefix requirement are all handled correctly.

Two high-severity issues were found: the pool dashboard burn rate computation uses the active session cost rather than the summed OVERAGE cost from the billing period, which is the wrong denominator for a billing-period burn rate; and the stale-cache logic has an off-by-one edge case that can anchor the wrong billing cycle start. Three medium issues cover a missing "est." prefix on pool_size display, the `**kwargs` pattern (carried from Phase 2) now silently sinking `pool_state`, and an unbounded config.json read on every cycle (also carried from Phase 2 but now amplified by a second file read). Two low-severity issues and three info items cover test gaps, docstring inaccuracies, and minor code quality points.

No critical (security/crash/data-loss) issues were found.

---

## High Severity

### HR-01: Pool burn rate uses active-session cost instead of billing-period pool spend rate

**File:** `ui/session_display.py:341-353`
**Issue:** The "Pool burn" row calculates `$/hr` as `(session_cost / elapsed_session_minutes) * 60`. This is the current active session's spend velocity, not the rate at which the overage pool is being consumed across the billing period. The two values can diverge significantly:

- `session_cost` is the cost of the single current session (may be $0.10).
- The pool burn rate the user cares about is the rate of pool-spending sessions over the billing period, or equivalently the rolling daily/hourly pool spend velocity.

More critically, `pool_state.pool_remaining_usd / burn_rate_per_hr` then produces a wildly inaccurate exhaustion time. If the current session is cheap but pool_spend_usd is large (many past OVERAGE sessions), the displayed "~Xh Ym remaining" will be far too optimistic.

The spec (D-09 in 03-CONTEXT.md) defines burn rate as "derived from the current active session: `session_cost_usd / elapsed_session_minutes × 60`". However, using this to project pool exhaustion compounds the error if the user's active session is cheap. The exhaustion time formula requires a burn rate measured in pool dollars per unit time, not per-session dollars per unit time.

**Fix:** Two options in order of correctness:
```python
# Option A (simplest, accurate enough for local estimate):
# Use pool_spend_usd divided by days elapsed in the billing period.
from datetime import date
cycle_start = date.fromisoformat(pool_state.billing_cycle_start)
days_elapsed = max(1, (date.today() - cycle_start).days)
burn_rate_per_hr = pool_state.pool_spend_usd / (days_elapsed * 24)

# Option B (spec-compliant but document the limitation):
# Keep the session-rate formula but label the exhaustion row clearly
# as "at current session rate" so users understand it is a snapshot.
exhaust_str = f"~{hours}h {mins}m at current session rate"
```
Option A is preferred because the exhaustion projection is then meaningful against the billing-period pool. Option B is the minimal change if the spec decision D-09 is intentional.

---

### HR-02: Stale cache detection has off-by-one: cached start equal to current start is retained when it should be recomputed

**File:** `core/pool_state_manager.py:207`
**Issue:** The stale-check condition is:
```python
if cached_start >= current_cycle_start:
    cycle_start = cached_start
```
This accepts `cached_start == current_cycle_start` as "not stale" and reuses the cached value, which is correct. However, it also accepts `cached_start > current_cycle_start`, meaning a cached start date in the **future** (relative to the computed cycle start) is silently used. This can happen if:

1. The user changed `billing_cycle_start_day` to an earlier day in config.json (e.g., from 15 to 1). Now `current_cycle_start` is day 1 but `cached_start` might be day 15 (a date after day 1 in the same month), so `cached_start > current_cycle_start` and the wrong (future) anchor is used.
2. Clock skew or manual file editing produces a future date.

In this case, sessions before the cached start are excluded from pool spend even though they fall within the actual billing period — underreporting pool spend.

**Fix:**
```python
# Accept cache only when cached_start equals current_cycle_start exactly,
# OR when cached_start is in the past but no newer cycle has started.
# The safe rule: only use cache if cached_start is not newer than current_cycle_start.
if cached_start <= current_cycle_start:
    # Use the more recent of the two (current_cycle_start always wins if >=)
    cycle_start = current_cycle_start
else:
    # cached_start is in the future — config changed or file corrupted; recompute
    logger.warning(
        "pool_spend.json billing_cycle_start=%s is in the future (current=%s) — recomputing",
        cached_start,
        current_cycle_start,
    )
    cycle_start = current_cycle_start
```
Alternatively, simply always prefer `current_cycle_start` (recompute from config on every cycle). The cache's value of `billing_cycle_start` is then informational only, and D-06 is satisfied by reading the cache for `pool_spend_usd` continuity (if you add that path). The current code discards the cached `pool_spend_usd` entirely anyway (it only uses `billing_cycle_start` from the cache), so removing the cache-start logic entirely has no behavioral regression.

---

## Medium Severity

### MD-01: "est." prefix missing on pool_size_usd in the pool spend row

**File:** `ui/session_display.py:325`
**Issue:** The pool spend row renders as:
```
🏦 Pool spent:   est. $12.34 / $500.00
```
The `est.` prefix applies to `pool_spend_usd` (the left side) but not to `pool_size_usd` (the right side, `$500.00`). `pool_size_usd` comes from `config.json` — it is the user-configured pool size, not an estimate. However, CLAUDE.md and the project requirements (DISP-02) state: "All displayed cost figures must include 'est.' prefix — they are local approximations, not authoritative billing data."

The denominator `$500.00` is a cost figure (the pool budget), so it should also carry the prefix to be consistent with the policy. The inconsistency also looks odd visually — a denominator without "est." implies it is authoritative when the whole figure is a local approximation.

**Fix:**
```python
screen_buffer.append(
    f"🏦 [value]Pool spent:[/]   est. ${pool_state.pool_spend_usd:.2f} / est. ${pool_state.pool_size_usd:.2f}"
)
```

---

### MD-02: `pool_state` passed via `**kwargs` inherits the silent-drop problem from Phase 2

**File:** `ui/session_display.py:315`
**Issue:** `pool_state` is read from `**kwargs` via `kwargs.get("pool_state")`. This is the same pattern flagged as WR-03 in the Phase 2 review for `threshold_state`. A misspelling at any call site (e.g., `pool_state_=...` or `poolstate=...`) causes the pool dashboard to silently not render, with no error, no log entry, and no test failure.

The Phase 2 review recommended promoting `threshold_state` to an explicit keyword argument. `pool_state` should receive the same treatment simultaneously, since adding it to `**kwargs` now means two silently-droppable keys.

**Fix:** Add `pool_state` as an explicit keyword argument alongside the recommended `threshold_state` fix from Phase 2:
```python
def format_active_session_screen(
    self,
    ...
    original_limit: int = 0,
    threshold_state: Optional["ThresholdState"] = None,
    pool_state: Optional["PoolState"] = None,
    cost_limit_p90: Optional[float] = None,
    messages_limit_p90: Optional[int] = None,
) -> list[str]:
```

---

### MD-03: config.json read on every monitoring cycle, now doubled

**File:** `core/pool_state_manager.py:196`
**Issue:** `compute_pool_state()` calls `_read_pool_config()` on every invocation, which opens and fully reads `config.json`. `compute_pool_state()` is called on every `_fetch_and_process_data()` cycle (default every 10 seconds), so config.json is now read twice per cycle — once by `_read_manual_override()` in threshold_manager.py and once by `_read_pool_config()` here. This was flagged as WR-04 in the Phase 2 review for threshold_manager.py, and the same concern applies here.

Additionally, there is no size guard, so an excessively large or malformed config file is fully read into memory on each cycle.

**Fix:** Add the same size guard recommended in Phase 2 WR-04:
```python
MAX_CONFIG_SIZE = 1 * 1024 * 1024  # 1 MB sanity limit
if config_file.stat().st_size > MAX_CONFIG_SIZE:
    logger.warning(
        "config.json exceeds size limit (%d bytes) — using defaults",
        config_file.stat().st_size,
    )
    return pool_size, cycle_day
with open(config_file, encoding="utf-8") as f:
    data = json.load(f)
```
Longer term, pass a shared config dict from the orchestrator to both `get_threshold()` and `compute_pool_state()` so the file is read once per cycle.

---

## Low Severity

### LW-01: Pool exhaustion time not shown when pool is depleted (pool_remaining_usd == 0.0)

**File:** `ui/session_display.py:345-351`
**Issue:** When `pool_state.pool_remaining_usd` is exactly `0.0` (pool exhausted), `burn_rate_per_hr / pool_remaining_usd` is `0.0 / burn_rate`, which produces `remaining_hrs = 0`. The display then shows `~0h 0m remaining` — which is technically correct but misleading. A depleted pool has no remaining time; the row should indicate exhaustion explicitly.

```python
if pool_state.pool_remaining_usd <= 0.0:
    exhaust_str = "pool exhausted"
elif burn_rate_per_hr > 0:
    ...
```

---

### LW-02: `test_billing_cycle_start_day_from_config` is fragile near cycle day

**File:** `tests/test_pool_state_manager.py:175-184`
**Issue:** The test writes `billing_cycle_start_day=15` and then asserts `cycle_start.day == 15`. This assertion is only valid when today's date is on or after the 15th of the current month. When run on days 1–14, `_derive_billing_cycle_start(15)` returns the **previous month's** 15th — a date with `day == 15`, so the assertion still passes. However, the test comment "billing_cycle_start has day=15 (or adjusted)" acknowledges this ambiguity.

The test is not currently broken, but it provides weaker coverage than it appears to: it does not verify that the correct month is returned, only the correct day. A more precise test would verify the full date.

**Fix:**
```python
from datetime import date

today = date.today()
expected_cycle_start = (
    today.replace(day=15) if today.day >= 15
    else (today.replace(day=1) - timedelta(days=1)).replace(day=15)
    # i.e., 15th of previous month
)
assert cycle_start == expected_cycle_start
```

---

## Info

### IN-01: `compute_pool_state()` docstring says `costUSD` is from `data/analysis.py:_create_base_block_dict()` but does not clarify it is the statusline-resolved value

**File:** `core/pool_state_manager.py:183`
**Issue:** The docstring mentions `costUSD` in the block keys list, which a future developer could confuse with the removed JSONL field. CLAUDE.md explicitly warns: "The `costUSD` field in session JSONL was removed upstream at v1.0.9." Adding a clarifying note prevents the confusion.

**Fix:** Extend the docstring:
```python
# costUSD is the statusline-resolved cost (data/analyzer.py sets block.cost_usd
# from statusline.jsonl; data/analysis.py serializes it as "costUSD"). Despite
# the legacy field name, the value is accurate. See CLAUDE.md D-08 / D-06.
```

---

### IN-02: `_write_pool_spend_cache` leaves a `.tmp` file on disk if `replace()` raises after `open()` succeeds

**File:** `core/pool_state_manager.py:164-169`
**Issue:** The atomic write pattern is:
```python
with open(temp_file, "w", ...) as f:
    json.dump(payload, f, indent=2)
temp_file.replace(final_path)
```
If `temp_file.replace(final_path)` raises (e.g., cross-device rename on certain Windows configurations, or a permissions error), the `.tmp` file is left on disk. On the next successful write, it will be overwritten, so this is not a data-loss risk. However, if the tool is killed mid-write repeatedly, orphaned `.tmp` files accumulate in `~/.claude-monitor/`.

This is a low-impact scenario (same pattern used by `LastUsedParams.save()` throughout the codebase). No fix is required for v1, but it is worth documenting.

---

### IN-03: Test suite does not cover the stale-cache acceptance path from pool_spend.json

**File:** `tests/test_pool_state_manager.py` (entire file)
**Issue:** There is no test exercising the branch at `pool_state_manager.py:203-214` where a valid (non-stale) `pool_spend.json` cache exists and its `billing_cycle_start` is reused. Test 12 verifies that the cache is written, but no test reads it back on a second call to verify the cache is honoured. A future refactor of the cache-read logic could silently break the D-06 behaviour with no test failure.

**Fix:** Add a test:
```python
def test_pool_spend_cache_billing_start_reused(tmp_path):
    """If pool_spend.json has a valid billing_cycle_start not older than current
    cycle, compute_pool_state() uses it rather than recomputing."""
    # Write a cache with today's billing_cycle_start
    today_str = date.today().isoformat()
    cache = tmp_path / "pool_spend.json"
    cache.write_text(json.dumps({
        "pool_spend_usd": 0.0,
        "billing_cycle_start": today_str,
        "last_updated": datetime.now().isoformat(),
    }))

    result = compute_pool_state([], KNOWN_STATE, config_dir=tmp_path)
    assert result.billing_cycle_start == today_str
```

---

_Reviewed: 2026-05-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
