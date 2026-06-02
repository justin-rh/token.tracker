---
phase: 10-historical-analytics
plan: 01
status: complete
completed: 2026-06-02
---

# Plan 10-01 Summary: Data Layer

## What was done

Added `daily_pool_spend` field to `PoolState` and daily bucketing to `compute_pool_state()`.

## Changes

- `core/pool_state_manager.py`:
  - Added `timedelta` to datetime import
  - Added `daily_pool_spend: tuple = ()` as last field on `PoolState` (default keeps existing callers valid)
  - Added `daily_spend: dict` accumulation inside the main block loop (same overage condition as `pool_spend_usd`)
  - Added post-loop range builder: all days from `cycle_start` to `today` using `timedelta(days=1)`, gaps filled with `0.0`
  - `PoolState` constructed with `daily_pool_spend=daily_pool_spend_tuple`

- `tests/test_pool_state_manager.py`:
  - Added `TestDailyPoolSpend` class with 6 tests covering: below-threshold blocks produce 0.0, single overage block bucketed correctly, multi-day buckets, zero-gap days included, calibrating state, gap blocks excluded

## Test results

- 6 new `TestDailyPoolSpend` tests: all pass
- 4 pre-existing failures (start_time="2026-05-08" outside June billing cycle) — unchanged
- No new regressions
