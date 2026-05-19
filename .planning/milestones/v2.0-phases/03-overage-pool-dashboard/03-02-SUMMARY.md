---
phase: 03-overage-pool-dashboard
plan: "02"
subsystem: wiring
tags: [pipeline-wiring, orchestrator, display-controller, cli]
dependency_graph:
  requires:
    - core/pool_state_manager.py (Plan 03-01 — PoolState + compute_pool_state())
  provides:
    - pool_state key in monitoring_data dict (orchestrator → display pipeline)
    - pool_state kwarg in create_data_display() signature
    - processed_data["pool_state"] passthrough to session_display kwargs
  affects:
    - ui/session_display.py (Plan 03-03 will read pool_state from kwargs to render rows)
tech_stack:
  added: []
  patterns:
    - three-hop data pipeline (orchestrator → display_controller → session_display) — mirrors identical threshold_state chain from Phase 2
    - Optional[T] = None kwarg pattern for new pipeline data without breaking existing callers
key_files:
  created: []
  modified:
    - monitoring/orchestrator.py
    - ui/display_controller.py
    - cli/main.py
decisions:
  - pool_state computed unconditionally (both custom and non-custom plans) — compute_pool_state handles threshold_state=None gracefully with $0.00 spend result
  - Optional[PoolState] = None default in create_data_display() — non-custom plan paths pass None silently through the chain without conditional logic
  - pool_state added immediately after threshold_state in both signature and processed_data — mirrors Phase 2 pattern exactly for consistency
metrics:
  duration: "~1 min"
  completed: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 3
requirements:
  - OVGE-05
  - OVGE-06
---

# Phase 03 Plan 02: Orchestrator Wiring Summary

**One-liner:** Three-hop pool_state pipeline wired — orchestrator calls compute_pool_state(), display_controller accepts and forwards it, cli/main.py passes it through — mirroring the identical threshold_state chain from Phase 2.

## What Was Built

Six targeted edits across three files establish the data flow path from `core/pool_state_manager.compute_pool_state()` through to `session_display.py`'s `**kwargs` dict, where Plan 03-03 will render the pool dashboard rows.

**monitoring/orchestrator.py** (3 edits):
- Import: `from claude_monitor.core.pool_state_manager import PoolState, compute_pool_state`
- Call: `pool_state: PoolState = compute_pool_state(blocks, threshold_state)` after the threshold block in `_fetch_and_process_data()`
- Dict key: `"pool_state": pool_state` added to `monitoring_data` alongside `threshold_state`

**ui/display_controller.py** (3 edits):
- Import: `from claude_monitor.core.pool_state_manager import PoolState`
- Signature: `pool_state: Optional[PoolState] = None` added to `create_data_display()` after `threshold_state`
- Passthrough: `processed_data["pool_state"] = pool_state` after the `threshold_state` passthrough line

**cli/main.py** (1 edit):
- `pool_state=monitoring_data.get("pool_state")` kwarg added to `create_data_display()` call in `on_data_update()`

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Wire compute_pool_state into orchestrator and monitoring_data | 843a4ac |
| 2 | Add pool_state to display_controller signature + processed_data; update cli/main.py | e2ff71f |

## Acceptance Criteria Verified

- [x] `grep "from claude_monitor.core.pool_state_manager import" monitoring/orchestrator.py` — match found
- [x] `grep "pool_state" monitoring/orchestrator.py` — 3 matches (import, call, dict key)
- [x] `grep "compute_pool_state(blocks" monitoring/orchestrator.py` — match found
- [x] `grep "pool_state" ui/display_controller.py` — 4 matches (import, signature, comment, processed_data assignment)
- [x] `grep "pool_state.*Optional" ui/display_controller.py` — match found
- [x] `grep 'processed_data\["pool_state"\]' ui/display_controller.py` — match found
- [x] `grep "pool_state=monitoring_data" cli/main.py` — match found
- [x] `python -m pytest tests/ -v` — 31 passed, 0 failed
- [x] `python -c "from monitoring.orchestrator import MonitoringOrchestrator; from ui.display_controller import DisplayController; print('All imports OK')"` — OK

## Deviations from Plan

None — plan executed exactly as written. All six edits match the exact code specified in the plan's `<action>` blocks. Zero regressions.

## Known Stubs

None. This plan only wires data flow — no UI rendering, no hardcoded values, no placeholder data. The `pool_state` value flowing through the pipeline is a real `PoolState` frozen dataclass computed from actual block data.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary changes. The three edits operate entirely within the existing in-process monitoring pipeline:
- T-03-06 mitigation confirmed: `compute_pool_state()` is called inside the existing `try/except Exception` block in `_fetch_and_process_data()` — any exception from pool state computation is caught, logged, and returns None without halting the monitoring loop.
- T-03-07/T-03-08 accepted as per plan threat model — in-process dict, no external serialization.

## Self-Check: PASSED

Files verified:
- FOUND: C:/Users/justin.rhoda/token.tracker/monitoring/orchestrator.py (pool_state present at lines 10, 190, 197)
- FOUND: C:/Users/justin.rhoda/token.tracker/ui/display_controller.py (pool_state present at lines 21, 209, 284, 285)
- FOUND: C:/Users/justin.rhoda/token.tracker/cli/main.py (pool_state present at line 196)

Commits verified:
- FOUND: 843a4ac (Task 1 — orchestrator wiring)
- FOUND: e2ff71f (Task 2 — display_controller + cli/main.py wiring)

Tests: 31 passed, 0 failed
