---
phase: 06-per-project-breakdown
plan: "03"
subsystem: monitoring/orchestrator
tags: [orchestrator, wire-up, project-breakdown, wave-3]
dependency_graph:
  requires: [compute_project_breakdown() in core/project_breakdown.py (Plan 06-02)]
  provides: [monitoring_data["project_breakdown"] on every monitoring cycle]
  affects: [ui/session_display.py (Plan 06-04)]
tech_stack:
  added: []
  patterns: [compute_pool_state() mirror pattern for new data service integration]
key_files:
  created: []
  modified:
    - monitoring/orchestrator.py
key_decisions:
  - "compute_project_breakdown() takes no arguments — uses its own defaults for data_path and config_dir"
  - "project_breakdown inserted after pool_state in monitoring_data dict — consistent ordering with Phase 3 pattern"
  - "No explicit type annotation on project_breakdown variable — matches implicit pool_state pattern"
metrics:
  duration: "~2 minutes"
  completed: "2026-05-19T20:11:34Z"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 6 Plan 03: Wire compute_project_breakdown() into Orchestrator Summary

**One-liner:** Two targeted edits to `monitoring/orchestrator.py` — import added and `compute_project_breakdown()` called after `compute_pool_state()`, result placed in `monitoring_data["project_breakdown"]` on every cycle.

## What Was Built

`monitoring/orchestrator.py` now imports `compute_project_breakdown` from `claude_monitor.core.project_breakdown` and calls it unconditionally on every monitoring cycle inside `_fetch_and_process_data()`. The result is stored under the `"project_breakdown"` key in `monitoring_data`, making it available to all registered UI callbacks. Follows the identical pattern established by `compute_pool_state()` in Phase 3.

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add import and wire compute_project_breakdown into orchestrator | 74ed61e | monitoring/orchestrator.py |

## Verification Results

- Import check: `python -c "from claude_monitor.monitoring.orchestrator import MonitoringOrchestrator; print('OK')"` → `OK`
- `grep -c "project_breakdown" monitoring/orchestrator.py` → `3` (import, call, dict key)
- `grep -n "from claude_monitor.core.project_breakdown import compute_project_breakdown" monitoring/orchestrator.py` → exactly 1 match (line 11)
- `grep -n "compute_project_breakdown()" monitoring/orchestrator.py` → exactly 1 match (line 207)
- `grep -n '"project_breakdown"' monitoring/orchestrator.py` → exactly 1 match (line 215)
- No other lines modified — confirmed by reading full file after edits

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — STRIDE mitigations from threat register reviewed:
- T-06-03-01: `compute_project_breakdown()` failure is caught by the outer try/except in `_fetch_and_process_data()` (lines 247-252); logs error, returns None — monitoring thread does not crash
- T-06-03-02: `project_breakdown` contains only project display names and token counts — no PII, no secrets; accepted

## Self-Check: PASSED

- `monitoring/orchestrator.py` modified and committed at 74ed61e
- Import `from claude_monitor.core.project_breakdown import compute_project_breakdown` present at line 11
- Call `project_breakdown = compute_project_breakdown()` present at line 207
- Dict key `"project_breakdown": project_breakdown` present at line 215
- Import check passes: `OK`
- No file deletions in commit
