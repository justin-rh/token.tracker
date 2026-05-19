---
phase: 05-system-tray
plan: "02"
subsystem: ui
tags: [pystray, pillow, system-tray, cli, main, wiring, integration, ctypes, signal]
dependency_graph:
  requires:
    - phase: 05-01
      provides: ui/tray_manager.py (TrayManager class with start/stop/update API)
    - phase: 04-06
      provides: cli/main.py (WebPoller wiring pattern to copy for TrayManager)
  provides:
    - cli/main.py (TrayManager wired in 5 locations: import, _tray_shutdown, init+start, update in callback, stop in finally)
  affects:
    - Phase 6 (Per-Project Breakdown) — cli/main.py is now the fully-wired entry point
tech-stack:
  added: []
  patterns:
    - TrayManager lifecycle follows WebPoller wiring skeleton exactly (init outside guard, start unconditionally, stop in finally with locals() guard)
    - _tray_shutdown() as module-level helper using signal.CTRL_C_EVENT for cross-thread shutdown
    - tray update injected at END of on_data_update try block, after live_display.update() — same pattern as all other callback injections

key-files:
  created: []
  modified:
    - cli/main.py

key-decisions:
  - "TrayManager started unconditionally (no org_id guard) — shows -- utilization until first WebPoller result; avoids blank-icon edge case"
  - "import os added to stdlib block alongside signal — required for os.kill() in _tray_shutdown()"
  - "PowerShell window staying on taskbar when launched inside a shell is a known v2.0 limitation, not a bug — ctypes GetConsoleWindow() returns the shell's HWND; behavior correct when launched directly"

patterns-established:
  - "Phase 5 wiring pattern: add module-level shutdown helper, init unconditionally before callback def, inject update at END of try block, stop with locals() guard in finally"

requirements-completed: [TRAY-01, TRAY-02, TRAY-03, TRAY-04, TRAY-05]

duration: ~20min
completed: "2026-05-19"
---

# Phase 5 Plan 02: TrayManager cli/main.py Wiring Summary

**TrayManager wired into cli/main.py at all 5 required locations (import, _tray_shutdown helper, init+start, update in callback, stop in finally); human smoke-test approved all 7 checkpoint items end-to-end.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-19T00:00:00Z
- **Completed:** 2026-05-19
- **Tasks:** 2 (Task 1: wiring; Task 2: human smoke-test checkpoint)
- **Files modified:** 1

## Accomplishments

- Added `import os` and `from claude_monitor.ui.tray_manager import TrayManager` to cli/main.py stdlib/monitoring import blocks
- Implemented `_tray_shutdown()` module-level helper using `signal.CTRL_C_EVENT` for safe cross-thread shutdown (pystray win32 message loop thread → main thread)
- Initialized TrayManager unconditionally after WebPoller block; injected `tray_manager.update()` at end of `on_data_update` try block; added `tray_manager.stop()` to finally block with `"tray_manager" in locals()` guard
- Human smoke-test approved all 7 items: icon appears, tooltip shows utilization%, right-click menu (Open Dashboard + Quit), left-click toggle, Quit exits cleanly, Ctrl+C exits cleanly, no ghost icons

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire TrayManager into cli/main.py** - `32cbd97` (feat)

(Task 2 was a human verification checkpoint — no code changes, no commit)

## Files Created/Modified

- `cli/main.py` — TrayManager wired at 5 locations: import, `_tray_shutdown()` helper, `tray_manager = TrayManager(...)` + `tray_manager.start()`, `tray_manager.update(...)` in `on_data_update`, `tray_manager.stop()` in finally block

## Decisions Made

1. **TrayManager started unconditionally** — No `if org_id:` guard wraps `TrayManager(...)`. The tray shows `--` utilization until the first WebPoller cycle (~5s). This avoids a blank-icon edge case when no org_id is configured yet.

2. **`import os` added** — `_tray_shutdown()` requires `os.kill()`. The existing cli/main.py did not import `os` at the module level; it was added to the stdlib block alongside `import signal`.

3. **PowerShell window stays on taskbar when launched inside a shell** — This is a known v2.0 limitation, not a bug. `ctypes.windll.kernel32.GetConsoleWindow()` returns the HWND of the host shell's console window when the app is launched from inside an existing PowerShell/cmd session. The hide/show behavior works correctly when the app is launched directly (e.g., via a desktop shortcut or the Windows Run dialog). Deferred to v2.1+ as a UX improvement.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Phase 5 is complete. Both plans (05-01 TrayManager core, 05-02 cli wiring) are done. All 5 TRAY requirements satisfied.

Phase 6 (Per-Project Breakdown) is ready to execute. Depends on Phase 4 (complete). cli/main.py is the fully-wired entry point with no known blockers.

**Known v2.0 limitation (deferred to v2.1+):** Left-click window toggle hides the PowerShell window when launched directly, but does not hide when launched inside an existing shell session — ctypes `GetConsoleWindow()` returns the outer shell's HWND in that case.

---
*Phase: 05-system-tray*
*Completed: 2026-05-19*

## Self-Check: PASSED

- `cli/main.py` modified: CONFIRMED (commit 32cbd97)
- Commit 32cbd97 exists: FOUND (`feat(05-02): wire TrayManager into cli/main.py`)
- All 5 wiring locations in cli/main.py: CONFIRMED by Task 1 automated verify (PASS output)
- Human checkpoint: 7/7 items approved
- TRAY-01 through TRAY-05: all satisfied
