---
phase: 05-system-tray
verified: 2026-05-19T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Left-click toggle hides/restores terminal when app is launched directly (not inside a shell session)"
    expected: "Left-clicking the tray icon hides the terminal window; left-clicking again restores it"
    why_human: "ctypes GetConsoleWindow() returns the outer shell HWND when launched from inside PowerShell/cmd. Toggle behavior is only correct when launched directly (desktop shortcut, Run dialog). Human must verify against this launch mode per the documented v2.0 limitation."
  - test: "Quit menu shuts down cleanly — no ghost icon, no hung process"
    expected: "Tray icon disappears immediately, terminal shows clean exit message, process exits, no ghost icon after hover"
    why_human: "Ghost icon absence and process exit completeness require real OS interaction. The 7-item checkpoint was human-approved but this status is preserved for formal traceability."
  - test: "Ctrl+C shutdown removes tray icon cleanly"
    expected: "Pressing Ctrl+C in the terminal removes tray icon and exits cleanly — identical to Quit menu path"
    why_human: "CTRL_C_EVENT cross-thread signaling and tray cleanup in the outer KeyboardInterrupt handler requires live runtime observation."
---

# Phase 5: System Tray Verification Report

**Phase Goal:** Persistent color-coded tray icon driven by web utilization %, with tooltip, right-click menu, left-click toggle, and clean shutdown
**Verified:** 2026-05-19
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A colored circle icon appears in the Windows system tray notification area when the app starts | VERIFIED | `tray_manager.start()` called unconditionally in `_run_monitoring()` (cli/main.py:207); `run_detached(setup=...)` confirmed in `ui/tray_manager.py:81`; setup callback sets `visible=True` after win32 message loop is ready |
| 2 | Hovering the tray icon shows a tooltip with utilization % and last sync time | VERIFIED | `_build_tooltip()` confirmed at `ui/tray_manager.py:132-144`; format "Token Tracker  {pct}%  \| Last sync: {HH:MM:SS}"; all 4 `_build_tooltip` tests pass including length-under-128 guard |
| 3 | Right-clicking shows a menu with "Open Dashboard" and "Quit" | VERIFIED | `pystray.Menu` defined at `ui/tray_manager.py:63-72`; "Toggle Dashboard" has `visible=False` hiding it from right-click; "Open Dashboard" and "Quit" are the only visible items |
| 4 | Left-clicking the tray icon toggles the terminal window visible/hidden | VERIFIED (with documented limitation) | `default=True` on Toggle Dashboard menu item at line 67 routes left-click to `_toggle_console()`; ctypes `GetConsoleWindow` + `IsWindowVisible` + `ShowWindow` pattern confirmed at lines 152-158; known v2.0 limitation: behavior is correct only when launched directly, not from inside an existing shell |
| 5 | Calling tray_manager.stop() removes the icon from the tray without leaving a ghost | VERIFIED | Idempotent `stop()` at lines 84-95 guards on `self._icon is not None and not self._stopped`; sets `self._stopped = True` then calls `icon.stop()` (NIM_DELETE via WM_STOP); called in `finally` block at cli/main.py:296-297 with `"tray_manager" in locals()` guard; additionally guarded in outer `except KeyboardInterrupt` block at lines 306-308 |
| 6 | TrayManager.update() changes the icon color: green <50%, yellow 50-75%, red >=75% | VERIFIED | `_utilization_to_color()` at lines 185-197; thresholds at lines 193-196 exactly match spec; all 6 threshold tests pass; update() is Lock-guarded (`with self._lock`) and wired into `on_data_update` callback at cli/main.py:240-245 |

**Score:** 6/6 truths verified (5/5 plan must-haves; 5/5 ROADMAP success criteria map 1:1 to the truths above)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `ui/tray_manager.py` | TrayManager class — pystray Icon lifecycle, Pillow circle icon, ctypes window toggle | VERIFIED | 198 lines; exports `TrayManager` class and `_utilization_to_color`; all required methods present; substantive implementation confirmed |
| `pyproject.toml` | pystray and Pillow declared under Phase 5 comment block | VERIFIED | `"pystray>=0.19.5"` and `"Pillow>=12.0.0"` present under `# Phase 5 additions:` comment, positioned after `"httpx>=0.27.0"` |
| `cli/main.py` | TrayManager wiring — import, init, start, update in callback, stop in finally | VERIFIED | All 5 wiring locations confirmed; syntax valid (`ast.parse` exits 0) |
| `tests/test_tray_manager.py` | 15 tests covering color thresholds, icon image, tooltip, update guard | VERIFIED | All 15 tests pass in 0.07s |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `TrayManager.update()` | `pystray Icon.icon + Icon.title setters` | `with self._lock` | WIRED | Lock at line 110; `self._icon.icon` and `self._icon.title` assigned inside lock at lines 111-112 |
| `TrayManager._quit()` | main thread KeyboardInterrupt | `os.kill(os.getpid(), signal.CTRL_C_EVENT)` | WIRED | `signal.CTRL_C_EVENT` at line 177; `OSError` fallback to `shutdown_callback` at lines 178-182 |
| `TrayManager._toggle_console()` | console HWND | `ctypes.windll.kernel32.GetConsoleWindow()` | WIRED | `GetConsoleWindow()` at line 152; null HWND guard at line 153; `IsWindowVisible` + `ShowWindow` at lines 155-158 |
| `on_data_update callback` | `tray_manager.update()` | `monitoring_data.get("web_usage")` | WIRED | cli/main.py lines 240-245; `web_usage.utilization_pct` passed when not None; `monitoring_data.get("last_web_sync")` passed as `last_sync` |
| `_run_monitoring finally block` | `tray_manager.stop()` | `"tray_manager" in locals()` guard | WIRED | cli/main.py lines 295-297; identical pattern to web_poller guard on line 292-293 |
| `_tray_shutdown()` | main thread KeyboardInterrupt | `os.kill(os.getpid(), signal.CTRL_C_EVENT)` | WIRED | cli/main.py lines 121-127; `import os` confirmed on line 7; `import signal` confirmed on line 8 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ui/tray_manager.py` (update) | `utilization_pct`, `last_sync` | `monitoring_data["web_usage"]` from `MonitoringOrchestrator` → `WebPoller.get_web_usage()` | Yes — WebPoller fetches from claude.ai API on 5-min cadence; orchestrator passes result through `monitoring_data` dict | FLOWING |
| `tray_manager._build_tooltip()` | `utilization_pct`, `last_sync` | same as above | Yes — tooltip reflects live `utilization_pct: float` from `WebUsageData` frozen dataclass | FLOWING |
| Initial icon (startup) | `0.0` (green) | hardcoded `_make_icon_image(0.0)` at start | Intentional default — not a stub; first `on_data_update` cycle (~5s) replaces with real data | STATIC (intentional) |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_utilization_to_color` thresholds correct | `python -c "from claude_monitor.ui.tray_manager import _utilization_to_color; assert _utilization_to_color(0.0)==(34,197,94); assert _utilization_to_color(50.0)==(234,179,8); assert _utilization_to_color(75.0)==(239,68,68); print('PASS')"` | PASS | PASS |
| TrayManager pure-logic smoke test | `python -c "... tray.update(50.0, None)..."` | ALL SMOKE TESTS PASSED | PASS |
| pyproject.toml has both Phase 5 deps | `tomllib` parse + dep check | pystray: `['pystray>=0.19.5']`, Pillow: `['Pillow>=12.0.0']` | PASS |
| All 15 TrayManager tests pass | `pytest tests/test_tray_manager.py -v` | 15 passed in 0.07s | PASS |
| Full 63-test suite passes | `pytest` | 63 passed in 0.50s | PASS |
| cli/main.py syntax valid | `ast.parse(open('cli/main.py').read())` | SYNTAX: OK | PASS |
| All 9 wiring structure checks | string presence checks in cli/main.py | All 9: OK | PASS |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| TRAY-01 | 05-01, 05-02 | Persistent tray icon; green <50%, yellow 50-75%, red >75% | SATISFIED | `_utilization_to_color()` thresholds verified; icon starts on `start()`, updates on every `on_data_update` cycle |
| TRAY-02 | 05-01, 05-02 | Tooltip with utilization % and last web sync time | SATISFIED | `_build_tooltip()` confirmed; tooltip wired to `Icon.title` inside lock; format contains both fields; length <128 chars |
| TRAY-03 | 05-01, 05-02 | Right-click menu: "Open Dashboard" + "Quit"; Quit = clean shutdown | SATISFIED | Menu items confirmed; `_quit()` calls `icon.stop()` then `os.kill(CTRL_C_EVENT)` with `OSError` fallback; human checkpoint approved |
| TRAY-04 | 05-01, 05-02 | Left-click toggles terminal window | SATISFIED (with documented v2.0 limitation) | `default=True` on Toggle Dashboard; `_toggle_console()` uses `GetConsoleWindow + ShowWindow`; limitation documented: HWND mismatch when launched from shell session |
| TRAY-05 | 05-01, 05-02 | No ghost icons on any exit path | SATISFIED | Idempotent `stop()` in `finally` block + outer `except KeyboardInterrupt` handler; `icon.stop()` posts WM_STOP → NIM_DELETE |

**Orphaned requirements check:** REQUIREMENTS.md maps TRAY-01 through TRAY-05 to Phase 5. All 5 are claimed by both 05-01-PLAN.md and 05-02-PLAN.md. No orphaned requirements.

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `cli/main.py:283-285` | `signal.pause()` with `(AttributeError, OSError)` fallback to `while True: time.sleep(1)` | Info | Intentional Windows compatibility pattern; `signal.pause()` raises `OSError` on Windows; fallback is correct and necessary. OSError catch added per code review fix CR-01. Not a stub. |
| `ui/tray_manager.py:73` | `self._make_icon_image(0.0)` — green icon on startup before real data | Info | Intentional initial state, not a stub. First `on_data_update` cycle replaces with real utilization data (~5s after launch). |

No blockers found. No stubs. No TODO/FIXME/PLACEHOLDER comments in phase files.

---

### Human Verification Required

#### 1. Left-Click Toggle (Direct Launch)

**Test:** Launch the app via a desktop shortcut or the Windows Run dialog (not from inside a PowerShell or cmd shell session), then left-click the tray icon.
**Expected:** The terminal window hides (disappears from taskbar). Left-clicking again restores it.
**Why human:** `ctypes.windll.kernel32.GetConsoleWindow()` returns the outer shell's HWND when the app is launched from inside an existing shell, not the app's own console HWND. The correct toggle behavior can only be confirmed when launched directly. This is documented as a v2.0 limitation in the 05-02 SUMMARY.

**Note:** Human smoke-test checkpoint in 05-02 Task 2 was approved for all 7 items. This item is flagged only to acknowledge the documented constraint for formal verification traceability. The implementation is correct per its specified behavior.

#### 2. Quit Menu — Clean Exit Confirmation

**Test:** Right-click the tray icon and select "Quit".
**Expected:** Tray icon disappears immediately; terminal shows "Monitoring stopped by user." or equivalent; process exits (prompt returns); no ghost icon remains after hovering the notification area.
**Why human:** Ghost icon absence after hover and process exit completeness require live OS interaction. Already approved in the human smoke-test checkpoint.

#### 3. Ctrl+C Shutdown — Tray Icon Removal

**Test:** With the app running and tray icon visible, press Ctrl+C in the terminal.
**Expected:** Tray icon is removed; clean exit; no ghost icon.
**Why human:** The outer `except KeyboardInterrupt` tray stop guard (cli/main.py:306-308) is a code path that requires live runtime verification. Already approved in human smoke-test.

---

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are verified programmatically. All 5 TRAY requirement IDs (TRAY-01 through TRAY-05) are satisfied. The 3 human verification items reflect behaviors that were already approved in the 7-item human smoke-test checkpoint but require human confirmation for formal verification status per the GSD protocol. The PowerShell HWND limitation is an explicitly documented v2.0 constraint, not a gap.

---

_Verified: 2026-05-19_
_Verifier: Claude (gsd-verifier)_
