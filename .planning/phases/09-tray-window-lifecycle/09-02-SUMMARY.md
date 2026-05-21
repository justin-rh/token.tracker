---
phase: 09-tray-window-lifecycle
plan: 02
subsystem: ui
tags: [ctypes, win32, setforegroundwindow, pystray, tray, tdd, wndproc]

# Dependency graph
requires:
  - phase: 09-01
    provides: "_install_close_guard() with WNDPROC subclassing, _wndproc_cb/_original_wndproc attrs"
provides:
  - SetForegroundWindow wiring in _show_console() and _toggle_console() restore branch (D-05/D-06)
  - TestCloseGuard class: 5 tests covering PID guard + WM_CLOSE callback behavior
affects: [phase-10-analytics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SetForegroundWindow after ShowWindow(SW_RESTORE): restore branch only, never hide branch"
    - "WNDPROC callback test strategy: patch ctypes.windll.* at module level, extract captured_cb from SetWindowLongPtrW call args, call directly"

key-files:
  created: []
  modified:
    - ui/tray_manager.py
    - tests/test_tray_manager.py

key-decisions:
  - "SetForegroundWindow added to restore path only — hide path intentionally omitted (D-05/D-06)"
  - "TestCloseGuard uses module-level ctypes patching (claude_monitor.ui.tray_manager.ctypes) distinct from Plan 01 tests which patched ctypes.windll directly"
  - "WNDPROC callback tests extract closure via SetWindowLongPtrW.call_args[0][2] and call directly — no WNDPROC type mock needed for callback tests"

# Metrics
duration: 2min
completed: 2026-05-21
---

# Phase 9 Plan 02: SetForegroundWindow + TestCloseGuard Summary

**SetForegroundWindow wired into tray restore paths and 5 new unit tests covering WM_CLOSE guard PID logic and callback behavior — double-click and Open Dashboard now bring window to foreground**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-21T17:25:16Z
- **Completed:** 2026-05-21T17:26:57Z
- **Tasks:** 2 (Task 1: SetForegroundWindow; Task 2 TDD: TestCloseGuard)
- **Files modified:** 2 (ui/tray_manager.py, tests/test_tray_manager.py)

## Accomplishments

- `_show_console()`: added `ctypes.windll.user32.SetForegroundWindow(hwnd)` after `ShowWindow(hwnd, SW_RESTORE)` — satisfies TRAY-04 Open Dashboard foreground requirement (D-05/D-06)
- `_toggle_console()`: added `SetForegroundWindow(hwnd)` in the else (restore) branch only — hide branch unchanged (D-05/D-06 explicitly requires restore path only)
- Updated docstrings on both methods to reference D-05/D-06 and TRAY-04
- `TestCloseGuard` class appended to `tests/test_tray_manager.py` with 5 tests:
  - `test_no_hwnd_skips_subclassing` — GetConsoleWindow=0 leaves attrs at defaults
  - `test_shell_owned_hwnd_skips_subclassing` — foreign PID skips SetWindowLongPtrW
  - `test_process_owned_hwnd_installs_wndproc` — own PID calls SetWindowLongPtrW with GWLP_WNDPROC
  - `test_wm_close_callback_returns_zero_and_hides` — WM_CLOSE hides window, returns 0, no CallWindowProcW
  - `test_non_wm_close_message_delegates_to_original` — non-WM_CLOSE forwards to CallWindowProcW, no ShowWindow
- Test suite: 33/33 pass (5 new + 28 pre-existing)

## Task Commits

1. **Task 1: SetForegroundWindow to _show_console() and _toggle_console() restore path** - `2434a58` (feat)
2. **Task 2: TestCloseGuard unit tests** - `0276111` (feat)

## Files Created/Modified

- `ui/tray_manager.py` — `_toggle_console()` restore branch and `_show_console()` now call `SetForegroundWindow(hwnd)` after `ShowWindow(hwnd, SW_RESTORE)`; updated docstrings reference D-05/D-06
- `tests/test_tray_manager.py` — `TestCloseGuard` class with 5 tests appended at end of file

## Decisions Made

- `SetForegroundWindow` is placed strictly in the restore branch of `_toggle_console` and unconditionally in `_show_console` — matches plan spec and D-05/D-06 intent
- `TestCloseGuard` uses a distinct patching approach (`claude_monitor.ui.tray_manager.ctypes.*`) from the Plan 01 tests (which used `ctypes.windll`) — this properly patches the module-level reference; both approaches work but the new tests are more module-isolated
- Callback extraction via `SetWindowLongPtrW.call_args[0][2]` provides direct access to the real WINFUNCTYPE-wrapped closure, enabling genuine behavioral testing without needing to mock WNDPROC type itself

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Requirements Completed

- TRAY-02: Double-clicking tray icon brings window to foreground (SetForegroundWindow via _toggle_console default action)
- TRAY-04: "Open Dashboard" restores and foregrounds window (SetForegroundWindow in _show_console)
- TRAY-03: Tooltip continues updating — unchanged, already satisfied by existing update() method

## Phase 9 Completion

All 4 TRAY requirements satisfied across Plans 01 and 02:
- TRAY-01: Color thresholds (Plan 01 / Phase 5)
- TRAY-02: Double-click to foreground (Plan 02 — this plan)
- TRAY-03: Quit menu item (Plan 01 / Phase 5)
- TRAY-04: Open Dashboard foreground + WM_CLOSE hide-to-tray (Plans 01+02)

## Self-Check: PASSED

- `ui/tray_manager.py` — file exists, SetForegroundWindow present at lines 184 and 195
- `tests/test_tray_manager.py` — TestCloseGuard at line 280, 33 tests pass
- Commit `2434a58` — Task 1 verified in git log
- Commit `0276111` — Task 2 verified in git log

---
*Phase: 09-tray-window-lifecycle*
*Completed: 2026-05-21*
