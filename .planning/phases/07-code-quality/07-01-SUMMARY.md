---
phase: 07-code-quality
plan: "01"
subsystem: pool_state_manager
tags: [date-injection, utc, tdd, test-determinism, billing-cycle]
dependency_graph:
  requires: []
  provides: [deterministic-billing-cycle-start, today-param-injection]
  affects: [core/pool_state_manager.py, tests/test_pool_state_manager.py]
tech_stack:
  added: []
  patterns: [optional-param-injection, tdd-red-green, utc-date-normalization]
key_files:
  created: []
  modified:
    - core/pool_state_manager.py
    - tests/test_pool_state_manager.py
decisions:
  - "_derive_billing_cycle_start defaults to datetime.now(timezone.utc).date() (UTC) not date.today() (local)"
  - "today param threaded from compute_pool_state to _derive_billing_cycle_start via keyword arg"
  - "Test 7 rewritten with injected today=date(2026,5,15) to eliminate date.today() + timedelta fragility"
metrics:
  duration: "~3 minutes"
  completed: "2026-05-20T20:59:09Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  tests_added: 2
  tests_modified: 1
  tests_total: 19
---

# Phase 7 Plan 01: Date-Skew and UTC Normalization Summary

**One-liner:** Added `today: date | None` injection param to `_derive_billing_cycle_start` and `compute_pool_state`, defaulting to `datetime.now(timezone.utc).date()` (UTC), with two new deterministic branch tests and rewritten Test 7.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED  | Failing test for today param | facfeb0 | tests/test_pool_state_manager.py |
| 1    | Add today param to production code | 1a444ac | core/pool_state_manager.py |
| 2    | Update tests to inject fixed today date | 95dfe8b | tests/test_pool_state_manager.py |

## What Was Done

### Task 1: Production code changes (`core/pool_state_manager.py`)

**`_derive_billing_cycle_start`** updated from:
```python
def _derive_billing_cycle_start(cycle_day: int) -> date:
    today = date.today()
```
To:
```python
def _derive_billing_cycle_start(cycle_day: int, today: date | None = None) -> date:
    if today is None:
        today = datetime.now(timezone.utc).date()
```

**`compute_pool_state`** updated to accept and thread the `today` param:
```python
def compute_pool_state(
    blocks: list,
    threshold_state,
    config_dir: Optional[Path] = None,
    today: Optional[date] = None,
) -> "PoolState":
    ...
    current_cycle_start = _derive_billing_cycle_start(cycle_day, today=today)
```

The orchestrator call site `compute_pool_state(blocks, threshold_state)` remains unchanged — `today` defaults to `None` which resolves to UTC date automatically.

### Task 2: Test changes (`tests/test_pool_state_manager.py`)

- **Test 7** rewritten: replaced `date.today() - timedelta(days=60)` with fixed dates `"2026-03-01T10:00:00"` (excluded) and `"2026-05-15T10:00:00"` (included), passing `today=date(2026, 5, 15)` to `compute_pool_state`
- **Test 18** added: `today=date(2026, 1, 15)` with `cycle_day=20` → previous-month branch → `billing_cycle_start == date(2025, 12, 20)`
- **Test 19** added: `today=date(2026, 3, 1)` with `cycle_day=1` → exact-match branch → `billing_cycle_start == date(2026, 3, 1)`

## Verification Results

```
tests/test_pool_state_manager.py: 19 passed
Full suite: 72 passed
```

All success criteria met:
- `_derive_billing_cycle_start(cycle_day: int, today: date | None = None)` — uses UTC default
- `compute_pool_state(..., today: Optional[date] = None)` — passes today through
- Test 7 uses injected `today=date(2026, 5, 15)` — no `date.today()` in billing period setup
- Tests 18 and 19 exercise previous-month and exact-match branches deterministically
- Full 72-test suite passes

## Deviations from Plan

**1. [Deviation] Test count is 19 not 20**

The plan anticipated 20 tests (17 + Test 7 update + Tests 18 + 19). The Task 1 RED gate test (`test_compute_pool_state_accepts_today_param`) was replaced by the more descriptive Tests 18 and 19 in Task 2, resulting in 19 total tests. The functionality the RED test was checking (today param accepted, billing_cycle_start=2026-05-01) is fully covered by Tests 18 and 19. No missing coverage.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. The `today` param is test-only injection; T-07-01-03 (accept disposition) applies.

## TDD Gate Compliance

- RED gate commit: facfeb0 `test(07-01): add failing test for compute_pool_state today param (RED)` — test failed with `TypeError: compute_pool_state() got an unexpected keyword argument 'today'`
- GREEN gate commit: 1a444ac `feat(07-01): add today param to _derive_billing_cycle_start and compute_pool_state` — all 18 tests passed
- Task 2 commit: 95dfe8b `feat(07-01): update tests to inject fixed today date for determinism` — 19 tests passed

## Self-Check: PASSED

Files exist:
- core/pool_state_manager.py — FOUND
- tests/test_pool_state_manager.py — FOUND
- .planning/phases/07-code-quality/07-01-SUMMARY.md — FOUND

Commits exist:
- facfeb0 — FOUND (RED gate)
- 1a444ac — FOUND (Task 1 GREEN)
- 95dfe8b — FOUND (Task 2)
