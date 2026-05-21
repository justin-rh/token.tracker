---
phase: 09-tray-window-lifecycle
plan: 01
subsystem: ui
tags: [ctypes, wndproc, win32, pystray, tray, windows-message-loop]

# Dependency graph
requires:
  - phase: 05-tray-icon
    provides: TrayManager with run_detached(), _toggle_console(), _show_console()
provides:
  - WM_CLOSE interception via WNDPROC subclassing in TrayManager._install_close_guard()
  - PID guard (D-04) skips subclassing when shell owns the console window
  - stop() restores original WNDPROC before icon teardown (D-08)
affects: [09-02-tray-window-lifecycle, phase-10-analytics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "WNDPROC subclassing: SetWindowLongPtrW + WINFUNCTYPE callback stored as instance attr to prevent GC"
    - "PID guard: GetWindowThreadProcessId ownership check before intercepting a window"
    - "Clean teardown: restore original proc pointer before stopping dependent subsystem"

key-files:
  created: []
  modified:
    - ui/tray_manager.py

key-decisions:
  - "Use SetWindowLongPtrW (64-bit-safe) and CallWindowProcW for WNDPROC subclassing"
  - "WM_CLOSE returns 0 and calls ShowWindow(SW_HIDE) — never calls DefWindowProc (would destroy window)"
  - "_install_close_guard() extracted as private method (not inlined) for testability"
  - "PID guard skips subclassing silently in shell context — no user-facing warning needed"

patterns-established:
  - "ctypes callback lifetime: always store WINFUNCTYPE callback as instance attribute to prevent CPython GC"
  - "WNDPROC teardown: always restore original proc before stopping icon to avoid dangling hook crash"

requirements-completed: [TRAY-01, TRAY-03]

# Metrics
duration: 3min
completed: 2026-05-21
---

# Phase 9 Plan 01: WM_CLOSE Close Guard Summary

**WM_CLOSE interception via WNDPROC subclassing — terminal window hides to tray instead of terminating when user presses X or Alt+F4**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-21T16:51:41Z
- **Completed:** 2026-05-21T16:54:36Z
- **Tasks:** 2 (Task 1 TDD: RED + GREEN; Task 2: wiring)
- **Files modified:** 2 (ui/tray_manager.py, tests/test_tray_manager.py)

## Accomplishments

- Added `WM_CLOSE`, `GWLP_WNDPROC`, `SW_SHOW` module constants and `WNDPROC` WINFUNCTYPE to `ui/tray_manager.py`
- Implemented `_install_close_guard()` with D-04 PID guard, WNDPROC callback (hide on WM_CLOSE, forward all other messages), and safe instance-attribute storage of both callback and original proc pointer
- Wired `_install_close_guard()` into `start()` after `run_detached()` (D-03) and added WNDPROC restore in `stop()` before `icon.stop()` (D-08)
- 13 new unit tests covering no-console, shell-context, and own-console branches via ctypes mocking; full suite 96/96 pass

## Task Commits

1. **RED — Failing tests for WM_CLOSE close guard** - `78fd05c` (test)
2. **Task 1: Constants, WNDPROC type, _install_close_guard()** - `92956d0` (feat)
3. **Task 2: Wire into start() and restore in stop()** - `bd1c218` (feat)

## Files Created/Modified

- `ui/tray_manager.py` — added WM_CLOSE/GWLP_WNDPROC/SW_SHOW constants, WNDPROC WINFUNCTYPE, `_wndproc_cb`/`_original_wndproc` init attrs, `_install_close_guard()` method, updated `start()` and `stop()`
- `tests/test_tray_manager.py` — added 4 new test classes (13 tests) for close guard behavior

## Decisions Made

- `_install_close_guard()` extracted as its own private method rather than inlined in `start()` — enables mocked unit testing of PID guard branches without pystray
- Used `SetWindowLongPtrW` (Unicode, 64-bit-safe) and `CallWindowProcW` per plan spec — consistent with Windows best practices
- WM_CLOSE handler returns 0 without calling `DefWindowProc` — this is correct Windows behavior for intercept-and-suppress

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `_install_close_guard()` is complete and tested; plan 09-02 can now add `SetForegroundWindow` to `_show_console()` / `_toggle_console()` (D-05, D-06) and end-to-end tests
- No blockers

---
*Phase: 09-tray-window-lifecycle*
*Completed: 2026-05-21*
