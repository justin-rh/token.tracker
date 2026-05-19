---
phase: 04-web-data-foundation
plan: "04"
subsystem: monitoring-pipeline
tags: [orchestrator, display-controller, web-usage, plumbing, phase-4]
dependency_graph:
  requires:
    - 04-03  # WebPoller daemon thread (provides get_web_usage() interface)
    - 04-01  # WebUsageData frozen dataclass in core/models.py
  provides:
    - MonitoringOrchestrator.set_web_poller  # callable by cli/main.py (04-06)
    - monitoring_data["web_usage"]           # consumed by display callback chain
    - create_data_display(web_usage=)        # kwarg available to session_display (04-05)
  affects:
    - ui/session_display.py  # receives web_usage via **processed_data in 04-05
    - cli/main.py            # will call set_web_poller() in 04-06
tech_stack:
  added: []
  patterns:
    - "Optional[Any] type annotation for cross-module instance (avoids circular import)"
    - "pool_state pattern replicated exactly for web_usage plumbing"
key_files:
  created: []
  modified:
    - monitoring/orchestrator.py
    - ui/display_controller.py
decisions:
  - "Used Optional[Any] for _web_poller type annotation to avoid circular import between orchestrator and web_poller modules"
  - "web_usage added immediately after pool_state in monitoring_data dict to maintain visual consistency with Phase 3 pattern"
metrics:
  duration: "285 seconds (~5 minutes)"
  completed: "2026-05-19"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  files_created: 0
---

# Phase 4 Plan 4: Orchestrator wire-up + display_controller kwarg pass-through Summary

WebPoller wired into the monitoring pipeline via two-file, three-change plumbing: `set_web_poller()` on orchestrator + `web_usage` in `monitoring_data` + `web_usage` kwarg on `create_data_display()`.

## What Was Built

Minimal plumbing connecting the WebPoller cache (04-03) to the display layer (04-05). Mirrors the Phase 3 `pool_state` pattern exactly:

- `MonitoringOrchestrator._web_poller` instance attribute (defaults to `None`)
- `MonitoringOrchestrator.set_web_poller(poller)` method for registration from `cli/main.py`
- `monitoring_data["web_usage"]` key populated on every callback cycle as `poller.get_web_usage() if poller else None`
- `create_data_display(web_usage: Optional[WebUsageData] = None)` parameter added to pass data into `processed_data`
- `processed_data["web_usage"] = web_usage` injection so `format_active_session_screen(**processed_data)` receives the value

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add set_web_poller() and web_usage to monitoring/orchestrator.py | 2f262aa | monitoring/orchestrator.py |
| 2 | Add web_usage kwarg pass-through in ui/display_controller.py | b0d158b | ui/display_controller.py |

## Decisions Made

- `Optional[Any]` used for `_web_poller` type annotation to avoid a circular import between `monitoring/orchestrator.py` and `monitoring/web_poller.py`. This is the same approach used for `_args`.
- `web_usage` added immediately after `pool_state` in the `monitoring_data` dict to maintain visual consistency with the Phase 3 pattern.

## Deviations from Plan

None — plan executed exactly as written. Both files required exactly the changes described in the plan interfaces block.

## Threat Mitigation Verification

- T-04-04-02 (DoS — _web_poller not set): `self._web_poller.get_web_usage() if self._web_poller else None` — None default implemented; no AttributeError possible when poller not registered.
- T-04-04-01 (Tampering — frozen dataclass): WebUsageData is `@dataclass(frozen=True)` — confirmed in core/models.py line 114.

## Known Stubs

None — this plan is pure plumbing. No display rows are rendered yet; `web_usage` flows through to `format_active_session_screen()` kwargs but 04-05 handles rendering.

## Self-Check: PASSED

Files modified exist:
- monitoring/orchestrator.py — FOUND
- ui/display_controller.py — FOUND

Commits exist:
- 2f262aa — feat(04-04): add set_web_poller() and web_usage to MonitoringOrchestrator
- b0d158b — feat(04-04): add web_usage kwarg pass-through in DisplayController
