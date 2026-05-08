---
phase: 03-overage-pool-dashboard
plan: "01"
subsystem: core
tags: [tdd, pool-accounting, persistence, frozen-dataclass]
dependency_graph:
  requires: []
  provides:
    - core/pool_state_manager.py (PoolState dataclass + compute_pool_state())
  affects:
    - monitoring/orchestrator.py (Plan 03-02 will wire compute_pool_state here)
    - ui/session_display.py (Plan 03-03 will render PoolState rows)
tech_stack:
  added: []
  patterns:
    - frozen dataclass (mirrors ThresholdState pattern from core/threshold_manager.py)
    - atomic write via .tmp rename (mirrors LastUsedParams.save() from core/settings.py)
    - config key validation with warning-on-bad-value (mirrors _read_manual_override())
key_files:
  created:
    - core/pool_state_manager.py
    - tests/test_pool_state_manager.py
  modified: []
decisions:
  - PoolState.is_overage reflects whether at least one OVERAGE session exists in billing period (not current session status)
  - compute_pool_state() writes pool_spend.json on every call (not startup-only) for crash resilience
  - Stale cache detection: cached billing_cycle_start < derived current cycle start → ignore cache, recompute
metrics:
  duration: "~2 min"
  completed: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 03 Plan 01: Pool State Manager Summary

**One-liner:** PoolState frozen dataclass + compute_pool_state() with OVERAGE billing-period accounting, atomic JSON cache, and config-driven pool_size/cycle_day with warning-on-bad-value fallbacks.

## What Was Built

`core/pool_state_manager.py` — the business logic foundation for Phase 3's overage pool dashboard. This module encapsulates all pool spend computation: reads `config.json` for `pool_size_usd` and `billing_cycle_start_day`, filters serialized block dicts to the current billing period, classifies sessions as INCLUDED vs OVERAGE by comparing `totalTokens` against `threshold_state.threshold_tokens`, sums OVERAGE `costUSD` values into `pool_spend_usd`, derives `pool_remaining_usd` and `pool_pct_spent`, and writes `pool_spend.json` atomically on every call.

`tests/test_pool_state_manager.py` — 14 unit tests covering all D-01 through D-10 decisions. TDD cycle completed: RED (ImportError) → GREEN (all 14 pass, 31 total, 0 regressions).

## TDD Gate Compliance

- RED gate commit: `a550cb4` — `test(03-01): add failing tests for pool_state_manager`
- GREEN gate commit: `3fb74c4` — `feat(03-01): implement core/pool_state_manager.py`
- REFACTOR: not needed — implementation was clean on first pass

## Tasks Completed

| Task | Type | Description | Commit |
|------|------|-------------|--------|
| 1 | RED | Write 14 failing tests (ImportError) | a550cb4 |
| 2 | GREEN | Implement pool_state_manager.py, all 14 tests pass | 3fb74c4 |

## Acceptance Criteria Verified

- [x] `core/pool_state_manager.py` exists with `class PoolState` and `def compute_pool_state`
- [x] `grep "temp_file.replace"` confirms atomic write present
- [x] `python -m pytest tests/test_pool_state_manager.py -v` → 14 passed, 0 failed
- [x] `python -m pytest tests/ -v` → 31 passed, 0 failed (no regressions)
- [x] `python -c "from core.pool_state_manager import PoolState, compute_pool_state; print('import OK')"`

## Deviations from Plan

None — plan executed exactly as written. All 14 tests from the spec were implemented verbatim, and the implementation followed the provided code templates without modification.

## Known Stubs

None. `pool_state_manager.py` is a pure computation module with no hardcoded placeholder values. All fields are derived from real inputs (blocks, config, date arithmetic).

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary changes introduced. Files created:
- `core/pool_state_manager.py` — local filesystem reads only (`~/.claude-monitor/config.json`, `pool_spend.json`). T-03-02 mitigation (config validation) and T-03-03 mitigation (write error handling) are both implemented as specified in the threat model.

## Self-Check: PASSED

Files verified:
- FOUND: C:/Users/justin.rhoda/token.tracker/core/pool_state_manager.py
- FOUND: C:/Users/justin.rhoda/token.tracker/tests/test_pool_state_manager.py

Commits verified:
- FOUND: a550cb4 (RED gate — test commit)
- FOUND: 3fb74c4 (GREEN gate — feat commit)
