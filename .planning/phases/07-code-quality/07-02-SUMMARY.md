---
phase: 07-code-quality
plan: 02
subsystem: testing
tags: [python, logging, pytest, caplog, tdd]

# Dependency graph
requires:
  - phase: 06-per-project-breakdown
    provides: core/project_breakdown.py with compute_project_breakdown() and display_name collision detection
provides:
  - slug_map local variable tracking first-seen slug per display_name inside compute_project_breakdown()
  - logger.warning with both colliding slugs when display_name collision occurs
  - test_display_name_collision_logs_warning_with_both_slugs test asserting WARNING level + both slug names
affects:
  - phase: 08-burn-rate
  - phase: 09-tray-lifecycle

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "slug_map pattern: local dict[str, str] tracks first-seen slug per display_name key, enabling collision identification"
    - "caplog.at_level pattern: pytest caplog fixture with explicit logger name for targeted log capture"

key-files:
  created: []
  modified:
    - core/project_breakdown.py
    - tests/test_project_breakdown.py

key-decisions:
  - "slug_map is a local variable (not module-level) — initialized alongside today_tokens/month_tokens; no persistence risk"
  - "Collision detection uses slug_map instead of today_tokens/month_tokens check — correctly identifies the FIRST slug that claimed the display_name"
  - "TDD order: test (RED) committed first, then implementation (GREEN) — gates verified by running pytest between commits"

patterns-established:
  - "TDD RED-GREEN pattern for logging behavior: write failing caplog assertion → implement logger.warning → verify GREEN"

requirements-completed:
  - QUAL-02

# Metrics
duration: 10min
completed: 2026-05-20
---

# Phase 7 Plan 02: Display-Name Collision WARNING Summary

**Bumped display_name collision log from DEBUG to WARNING in project_breakdown.py using slug_map dict to identify both colliding project slugs**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-20T00:00:00Z
- **Completed:** 2026-05-20T00:10:00Z
- **Tasks:** 2 (Task 1: implementation, Task 2: test — executed RED-GREEN TDD)
- **Files modified:** 2

## Accomplishments
- Added `slug_map: dict[str, str] = {}` local variable to `compute_project_breakdown()` alongside `today_tokens` and `month_tokens`
- Replaced `logger.debug` collision log (single slug, silent at WARNING level) with `logger.warning` that names both the original and current colliding slugs
- Added `test_display_name_collision_logs_warning_with_both_slugs` — asserts WARNING level emitted, both slug names present, "collision" keyword present
- Full test suite: 71 tests pass (8 project_breakdown tests, up from 7)

## Task Commits

Each task was committed atomically following TDD RED-GREEN sequence:

1. **RED — Failing test for collision WARNING** - `73a38e1` (test)
2. **GREEN — slug_map + logger.warning implementation** - `91733fb` (feat)

_Note: TDD tasks committed in RED (test) then GREEN (impl) order per TDD execution flow._

## Files Created/Modified
- `core/project_breakdown.py` - Added `slug_map: dict[str, str] = {}`, replaced `logger.debug` with `logger.warning` including both slug names; collision detection now uses `if display_name in slug_map` instead of `if display_name in today_tokens or display_name in month_tokens`
- `tests/test_project_breakdown.py` - Added `test_display_name_collision_logs_warning_with_both_slugs` (Test 8) with caplog assertions for WARNING level and both slug names

## Decisions Made
- `slug_map` implemented as a local `dict[str, str]` (not module-level state) so it resets per invocation — no cross-call contamination
- Collision detection logic uses `slug_map` as the source of truth (not `today_tokens`/`month_tokens`) because those dicts only exist if tokens were already accumulated; `slug_map` tracks the first slug unconditionally

## Deviations from Plan

None — plan executed exactly as written. TDD RED-GREEN sequence applied as specified.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- QUAL-02 complete; project_breakdown collision logging is now user-visible at WARNING level
- Ready for Phase 7 remaining plans (07-01, 07-03) in the same wave
- `core/project_breakdown.py` is stable; no further changes expected for Phase 8 or 9

---
*Phase: 07-code-quality*
*Completed: 2026-05-20*

## Self-Check

### Created files exist:
- `.planning/phases/07-code-quality/07-02-SUMMARY.md` — this file

### Modified files exist:
- `core/project_breakdown.py` — slug_map at line 146, logger.warning at line 155
- `tests/test_project_breakdown.py` — test_display_name_collision_logs_warning_with_both_slugs at line 288

### Commits exist:
- `73a38e1` — test(07-02): add failing test for display_name collision WARNING
- `91733fb` — feat(07-02): bump display_name collision log to WARNING with both slugs

### Test results:
- 8/8 project_breakdown tests pass
- 71/71 full suite passes

## Self-Check: PASSED
