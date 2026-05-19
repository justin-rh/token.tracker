---
phase: 05-system-tray
plan: "01"
subsystem: ui
tags: [pystray, pillow, system-tray, tray-icon, ctypes, threading]
dependency_graph:
  requires:
    - core/models.py (WebUsageData.utilization_pct: float)
    - monitoring/web_poller.py (structural analog for Lock/start/stop pattern)
  provides:
    - ui/tray_manager.py (TrayManager class — pystray Icon lifecycle, Pillow circle icon, ctypes window toggle)
    - pyproject.toml (pystray>=0.19.5 and Pillow>=12.0.0 declared under Phase 5 comment block)
  affects:
    - cli/main.py (Plan 05-02 wires TrayManager.start()/stop()/update() here)
tech_stack:
  added:
    - pystray==0.19.5 (system tray icon via win32 NOTIFYICONDATA)
    - Pillow==12.2.0 (PIL Image creation for tray icon)
  patterns:
    - WebPoller Lock/start/stop skeleton replicated in TrayManager
    - icon.run_detached() with setup callback for race-free visible=True
    - _utilization_to_color() pure function (testable without pystray Icon)
key_files:
  created:
    - ui/tray_manager.py
    - tests/test_tray_manager.py
  modified:
    - pyproject.toml
decisions:
  - icon.run_detached() not run() — run() blocks calling thread; run_detached() is the supported integration path (per STATE.md, RESEARCH.md)
  - TrayManager is NOT a Thread subclass — it is a plain object; the win32 backend internally spawns its own thread via run_detached()
  - setup callback sets visible=True (not post-call assignment) — eliminates race where visible setter fires before _hwnd is created
  - CTRL_C_EVENT not SIGINT for Quit — SIGINT is not reliable on Windows from non-main threads; CTRL_C_EVENT raises KeyboardInterrupt in main thread
  - OSError fallback in _quit() — if CTRL_C_EVENT fails, shutdown_callback is called directly
  - _utilization_to_color() extracted as module-level function — enables direct testing without pystray Icon instantiation
metrics:
  duration: "3m 13s"
  completed: "2026-05-19"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 5 Plan 01: TrayManager Core Summary

**One-liner:** pystray Icon wrapper with Pillow color-coded circle icon (green/yellow/red), ctypes window toggle, and CTRL_C_EVENT shutdown via `icon.run_detached()` — not a Thread subclass.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add pystray and Pillow to pyproject.toml | 1f9c411 | pyproject.toml |
| TDD RED | Failing tests for TrayManager | 63f956c | tests/test_tray_manager.py |
| 2 | Create ui/tray_manager.py | 3ca9351 | ui/tray_manager.py |

## Verification Results

```
pystray ok | Pillow 12.2.0
PASS — TrayManager core verified
PASS — pyproject.toml has both dependencies
```

All 15 pytest tests pass:
- 6 tests: `_utilization_to_color()` threshold boundaries (0.0, 49.9, 50.0, 74.9, 75.0, 100.0)
- 4 tests: `_make_icon_image()` RGBA mode, 64x64 size, center pixel color per threshold
- 4 tests: `_build_tooltip()` content format and 128-char NIF_TIP limit
- 1 test: `update()` no-op guard when `_icon is None`

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | 63f956c | PASS — 15 tests failed before implementation |
| GREEN (feat) | 3ca9351 | PASS — 15 tests pass after implementation |
| REFACTOR | n/a | No refactor needed — code is clean on first pass |

## Decisions Made

1. **`run_detached()` + setup callback** — The `setup=lambda icon: setattr(icon, 'visible', True)` pattern fires only after the win32 message loop marks ready, eliminating the race condition where `icon.visible = True` was called before `_hwnd` was initialized. (RESEARCH.md Pitfall 1)

2. **`_utilization_to_color()` as module-level function** — Extracted from `_make_icon_image()` to be independently testable. This avoids needing a pystray `Icon` instance in tests, which would attempt win32 API calls in headless CI environments.

3. **`signal.CTRL_C_EVENT` with `OSError` fallback** — Per RESEARCH.md Pitfall 3, `signal.SIGINT` is not valid on Windows via `os.kill`. `CTRL_C_EVENT` (= 0) raises `KeyboardInterrupt` in the main thread. The `OSError` fallback to `shutdown_callback` covers edge cases (e.g., process group isolation).

4. **`Callable` import from `typing`** — Used for `shutdown_callback` type annotation. Avoids `from collections.abc import Callable` which requires Python 3.9+ import path change (though 3.12 is in use, `typing.Callable` is cleaner for consistency with existing codebase patterns).

## Deviations from Plan

None — plan executed exactly as written.

The only minor note: `pystray.__version__` is not exposed as a module attribute (no `__version__` in pystray 0.19.5), so the verification command uses `pystray ok` instead of printing a version number. Both packages are importable and functional.

## Known Stubs

None — all logic is fully implemented. No hardcoded empty values or placeholder text. The initial tray icon uses `_make_icon_image(0.0)` (green circle) which is intentional (no data yet on startup, not a stub).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced.

Threat mitigations confirmed implemented per threat register:
- **T-05-01** (Information Disclosure): `_build_tooltip()` format is `"Token Tracker  {pct}%  |  Last sync: {HH:MM:SS}"` — no sessionKey or org_id in tooltip string. Confirmed by test `test_with_values_contains_pct_and_time`.
- **T-05-02** (Denial of Service / ghost icon): `stop()` is guarded with `if self._icon is not None` and calls `icon.stop()` which posts WM_STOP → `_mainloop()` finally → `_hide()` (NIM_DELETE). The `finally` block guard in `cli/main.py` (Plan 05-02) will complete T-05-02.
- **T-05-03** (Elevation of Privilege): `ctypes.windll.kernel32.GetConsoleWindow()` returns HWND of own process console only. Null HWND guard `if not hwnd: return` prevents ShowWindow(NULL, ...) call.
- **T-05-04** (Tampering / Quit): Accepted — intentional user action, no privilege escalation possible.
- **T-05-05** (Information Disclosure / logging): `logger.debug()` in `update()` logs only `utilization_pct` float. sessionKey is never referenced or logged in this module.

## Self-Check: PASSED

- `ui/tray_manager.py` exists: FOUND
- `tests/test_tray_manager.py` exists: FOUND
- `pyproject.toml` updated: FOUND (pystray>=0.19.5, Pillow>=12.0.0)
- Commit 1f9c411 exists: FOUND (chore(05-01): add pystray and Pillow)
- Commit 63f956c exists: FOUND (test(05-01): failing tests)
- Commit 3ca9351 exists: FOUND (feat(05-01): implement TrayManager)
- All 15 tests pass: CONFIRMED
- Full verification smoke test: PASS
