---
plan: 08-01
phase: 08-burn-rate-accuracy
status: complete
completed: 2026-05-20
commit: e4bbd3d
---

# Plan 08-01 Summary: Ring Buffer Burn Rate in Orchestrator

## What Was Built

Added rolling ring-buffer burn rate computation to `MonitoringOrchestrator` so the dashboard receives `pool_burn_rate_usd_per_hr` derived from actual `pool_spend_usd` velocity rather than session cost / uptime.

## Key Changes

**`monitoring/orchestrator.py`**
- Added `import collections` to stdlib imports
- Added three instance attributes in `__init__`:
  - `self._burn_rate_buffer: collections.deque` — stores `(timestamp, pool_spend_usd)` tuples
  - `self._last_burn_sample_spend: float = 0.0` — dedup sentinel (only insert on strict increase)
  - `self._last_billing_cycle_start: Optional[str] = None` — detect billing cycle resets
- In `_fetch_and_process_data()`, inserted three-step block before `monitoring_data` assembly:
  1. Billing cycle reset detection — clears buffer and resets sentinel when `billing_cycle_start` changes
  2. Sample insertion — appends `(time.time(), pool_spend_usd)` only when spend strictly increases
  3. Burn rate computation — filters buffer to 30-minute window; returns `float` when ≥2 samples, `None` otherwise
- Added `"pool_burn_rate_usd_per_hr": burn_rate_usd_per_hr` key to `monitoring_data` dict

## Verification

- Inline: `python -c "... assert isinstance(o._burn_rate_buffer, collections.deque) ..."` → PASS
- Full suite: `python -m pytest tests/ -x -q` → 79 passed

## Self-Check: PASSED

All must_haves satisfied:
- `pool_burn_rate_usd_per_hr` key present in `monitoring_data` after every `_fetch_and_process_data()` call
- Value is `None` when fewer than 2 samples exist in the 30-minute window
- Computed from oldest+newest filtered pair: `delta_spend / delta_time_hours`
- Samples appended only when `pool_spend_usd` strictly increases
- Buffer cleared when `billing_cycle_start` changes
