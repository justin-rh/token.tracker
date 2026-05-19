---
phase: 02-threshold-detection
plan: 02
subsystem: threshold-detection
tags: [python, orchestrator, threshold-manager, monitoring-data]

# Dependency graph
requires:
  - phase: 02-threshold-detection
    plan: 01
    provides: ThresholdState frozen dataclass; get_threshold() function
  - phase: 01-windows-foundation
    provides: monitoring/orchestrator.py MonitoringOrchestrator class
provides:
  - threshold_state key in monitoring_data dict (ThresholdState | None)
  - token_limit overridden from ThresholdManager result for custom plan (not bare P90)
  - Cold-start guard in orchestrator: token_limit = DEFAULT_TOKEN_LIMIT during calibration
affects: [02-03, display_controller, overage-pool-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Minimal-change integration: 3 edits only (import, computation block, dict key) — no rewrites"
    - "threshold_state=None for non-custom plans as explicit sentinel — callbacks must guard with `if threshold_state is not None`"
    - "token_limit stays int throughout — backward compat with all existing progress bar math"

key-files:
  created: []
  modified:
    - monitoring/orchestrator.py

key-decisions:
  - "[02-02] threshold_state=None for non-custom plans — avoids conditional logic in all callers; None is unambiguous 'not applicable'"
  - "[02-02] token_limit overridden from ThresholdManager for custom plan — supersedes bare P90 call that had no cold-start guard"
  - "[02-02] ThresholdManager call placed after _calculate_token_limit() — fallback int is already set before override logic runs"

# Metrics
duration: 1min
completed: 2026-05-08
---

# Phase 2 Plan 02: Orchestrator ThresholdManager Integration Summary

**ThresholdManager wired into monitoring/orchestrator.py — threshold_state added to monitoring_data dict with cold-start-safe token_limit override for custom plan**

## Performance

- **Duration:** 1 min
- **Started:** 2026-05-08T18:53:18Z
- **Completed:** 2026-05-08T18:54:02Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `from claude_monitor.core.threshold_manager import ThresholdState, get_threshold` import to `monitoring/orchestrator.py`
- Added `get_threshold(blocks)` call inside `_fetch_and_process_data()` for custom plan, immediately after the existing `_calculate_token_limit()` call
- Overrides `token_limit` with `DEFAULT_TOKEN_LIMIT` (19,000) when `threshold_state.status == "calibrating"` — prevents division-by-zero and misleading progress bar percentages during cold-start
- Overrides `token_limit` with `threshold_state.threshold_tokens` when status is `"auto"` or `"manual"` — ThresholdManager result is authoritative over bare P90 (which had no cold-start guard)
- Adds `"threshold_state"` key to `monitoring_data` dict alongside existing `"token_limit"` key
- Non-custom plans receive `threshold_state = None` — explicit sentinel that downstream callbacks can guard with `if threshold_state is not None`
- All non-custom code paths and the `_calculate_token_limit()` method left completely unchanged

## Task Commits

1. **Task 1: Wire ThresholdManager into orchestrator monitoring_data** — `a4f2ae2` (feat)

## Files Created/Modified

- `monitoring/orchestrator.py` — 3 edits: import added, get_threshold() computation block added, threshold_state key added to monitoring_data dict

## Decisions Made

- `threshold_state = None` for non-custom plans is an explicit value, not a missing key — downstream callers get a predictable dict shape regardless of plan type
- `token_limit` override placed inside the `_fetch_and_process_data()` try/except block — any exception from `get_threshold()` propagates to the existing outer handler that logs and returns None, satisfying T-02-06 (DoS mitigation)
- `_calculate_token_limit()` left unchanged — still used as the initial int value for all plan types; ThresholdManager then selectively overrides for custom plan

## Deviations from Plan

None — plan executed exactly as written. All three edits match the specification in the plan's `<action>` block verbatim.

## Known Stubs

None — no placeholder values or hardcoded empty data introduced.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. The `get_threshold()` call reads only from local filesystem paths already accessed by the existing monitoring pipeline.

---
*Phase: 02-threshold-detection*
*Completed: 2026-05-08*

## Self-Check: PASSED

- `monitoring/orchestrator.py` exists: FOUND
- Commit `a4f2ae2` exists: FOUND
- `from claude_monitor.core.threshold_manager import ThresholdState, get_threshold` in orchestrator.py: FOUND (line 9)
- `get_threshold(blocks)` call in orchestrator.py: FOUND (line 177)
- `threshold_state` key in monitoring_data dict: FOUND (line 192)
- `python -c "from monitoring.orchestrator import MonitoringOrchestrator; print('import OK')"`: PASSED
