---
phase: 09-tray-window-lifecycle
verified: 2026-05-21T18:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Close the terminal window (press X or Alt+F4) while token tracker is running"
    expected: "Window disappears; tray icon remains visible in the system notification area; process is still running (can restore from tray)"
    why_human: "WM_CLOSE interception requires a live Windows console window and pystray message loop — cannot simulate with unit tests alone"
  - test: "Double-click the tray icon while the window is hidden"
    expected: "Terminal window reappears in the foreground (not just un-hidden behind other windows)"
    why_human: "SetForegroundWindow behavior depends on Windows focus-steal prevention rules that vary by OS context — unit tests mock ctypes"
  - test: "Observe tray icon tooltip while window is hidden; wait for next monitoring cycle"
    expected: "Tooltip text updates to a new utilization % and Last sync timestamp on each cycle"
    why_human: "Tooltip liveness requires a running monitoring thread and live data — cannot verify statically"
  - test: "Right-click tray icon, select 'Open Dashboard' while window is hidden"
    expected: "Terminal window is restored and brought to the foreground"
    why_human: "pystray menu callback wiring and SetForegroundWindow interaction require a real tray session"
---

# Phase 9: Tray Window Lifecycle Verification Report

**Phase Goal:** Users can close the terminal window to minimize the app to the tray, and restore it from the tray without restarting the process
**Verified:** 2026-05-21T18:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                          | Status     | Evidence                                                                                                          |
|----|-----------------------------------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------------------------------------|
| 1  | Closing the terminal window hides it rather than terminating the process; tray icon stays     | VERIFIED   | `_install_close_guard()` returns 0 on WM_CLOSE + calls `ShowWindow(SW_HIDE)` (line 233-235); never calls `DefWindowProc`; PID guard skips subclassing in shell context (lines 218-227) |
| 2  | Double-clicking the tray icon brings the hidden window back to the foreground                 | VERIFIED   | `_toggle_console()` is `default=True` menu item (line 82-83); restore branch calls `SetForegroundWindow(hwnd)` (line 184) |
| 3  | Tray icon tooltip continues updating with current utilization % while window is hidden        | VERIFIED   | `update()` unconditionally sets `self._icon.title = self._build_tooltip(...)` (line 137); no window-visibility gate |
| 4  | Selecting "Open Dashboard" from tray right-click menu restores hidden window to foreground    | VERIFIED   | `_show_console()` calls `ShowWindow(hwnd, SW_RESTORE)` then `SetForegroundWindow(hwnd)` (lines 194-195); wired to "Open Dashboard" menu item (line 86) |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact                        | Expected                                                                      | Status    | Details                                                                                     |
|---------------------------------|-------------------------------------------------------------------------------|-----------|---------------------------------------------------------------------------------------------|
| `ui/tray_manager.py`            | `_install_close_guard()` with WM_CLOSE/GWLP_WNDPROC/SW_SHOW constants; WNDPROC ctypes type | VERIFIED  | All six symbols present; method at line 197; constants at lines 27-38                     |
| `ui/tray_manager.py`            | `_show_console()` and `_toggle_console()` with `SetForegroundWindow` after restore `ShowWindow` | VERIFIED | `SetForegroundWindow` at lines 184 and 195; only in restore paths                        |
| `tests/test_tray_manager.py`    | `TestCloseGuard` class with PID guard and WM_CLOSE callback behavior tests   | VERIFIED  | Class at line 280 with 5 tests covering all decision branches                              |

### Key Link Verification

| From                        | To                                          | Via                                         | Status  | Details                                                                  |
|-----------------------------|---------------------------------------------|---------------------------------------------|---------|--------------------------------------------------------------------------|
| `TrayManager.start()`       | `_install_close_guard()`                    | Direct method call after `run_detached()`   | WIRED   | Line 99: `self._install_close_guard()` after `run_detached()` at line 97 |
| `TrayManager.stop()`        | `SetWindowLongPtrW(hwnd, GWLP_WNDPROC, _original_wndproc)` | ctypes call before `icon.stop()` | WIRED   | Lines 112-118: guard + restore before `self._icon.stop()` at line 119   |
| `_show_console()`           | `SetForegroundWindow(hwnd)`                 | ctypes call after `ShowWindow(SW_RESTORE)`  | WIRED   | Lines 194-195 — sequential calls in hwnd guard block                     |
| `_toggle_console()` restore | `SetForegroundWindow(hwnd)`                 | ctypes call after `ShowWindow(SW_RESTORE)` in else branch | WIRED | Lines 183-184 — only in else (restore) branch; hide branch clean |

### Data-Flow Trace (Level 4)

| Artifact            | Data Variable       | Source                              | Produces Real Data | Status   |
|---------------------|---------------------|-------------------------------------|--------------------|----------|
| `ui/tray_manager.py` `update()` | `utilization_pct`, `last_sync` | Caller (MonitoringThread on_data_update callback) | Yes — passed in from live data pipeline | FLOWING |
| `_build_tooltip()`  | `util_str`, `sync_str`         | Parameters from `update()`          | Yes — real pct and datetime values      | FLOWING  |

### Behavioral Spot-Checks

| Behavior                               | Command                                                                    | Result           | Status  |
|----------------------------------------|----------------------------------------------------------------------------|------------------|---------|
| File parses without syntax errors      | `python -c "import ast; ast.parse(open('ui/tray_manager.py').read())"`     | `AST OK`         | PASS    |
| All 33 unit tests pass                 | `python -m pytest tests/test_tray_manager.py -v`                           | 33 passed in 0.10s | PASS  |
| WM_CLOSE constant value correct        | Test `TestInstallCloseGuardConstants::test_wm_close_value`                 | PASSED           | PASS    |
| GWLP_WNDPROC constant value correct    | Test `TestInstallCloseGuardConstants::test_gwlp_wndproc_value`             | PASSED           | PASS    |
| WM_CLOSE callback hides and returns 0  | Test `TestCloseGuard::test_wm_close_callback_returns_zero_and_hides`       | PASSED           | PASS    |
| Non-WM_CLOSE delegates to original     | Test `TestCloseGuard::test_non_wm_close_message_delegates_to_original`     | PASSED           | PASS    |

### Requirements Coverage

| Requirement | Source Plan | Description                                                          | Status    | Evidence                                                                                     |
|-------------|-------------|----------------------------------------------------------------------|-----------|----------------------------------------------------------------------------------------------|
| TRAY-01     | 09-01       | User can close terminal window; app continues in tray               | SATISFIED | `_install_close_guard()` intercepts WM_CLOSE, hides window, does not terminate              |
| TRAY-02     | 09-02       | User can double-click tray icon to restore terminal window          | SATISFIED | `_toggle_console()` is `default=True` (left-click); restore branch calls `SetForegroundWindow` |
| TRAY-03     | 09-01/09-02 | Tray tooltip updates while window is hidden                         | SATISFIED | `update()` sets `self._icon.title` unconditionally; no window-visibility gate               |
| TRAY-04     | 09-02       | "Open Dashboard" right-click item restores hidden window            | SATISFIED | `_show_console()` wired to menu item; calls `ShowWindow(SW_RESTORE)` + `SetForegroundWindow` |

All 4 required IDs (TRAY-01, TRAY-02, TRAY-03, TRAY-04) accounted for and satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TODOs, placeholders, stub returns, or hardcoded empty values found in phase-modified files.

### Human Verification Required

#### 1. WM_CLOSE Hide-to-Tray (TRAY-01 end-to-end)

**Test:** Launch `python -m claude_monitor`, wait for tray icon to appear, then press Alt+F4 or click the X button on the terminal window.
**Expected:** Terminal window disappears; tray icon remains in the notification area; no Python process exit occurs (verify via Task Manager or that the tray icon is still updating).
**Why human:** WM_CLOSE interception requires a live console window with a running pystray message loop. The unit tests mock ctypes; they cannot verify that `GetConsoleWindow()` returns the correct HWND or that the Windows message pump delivers WM_CLOSE to the subclassed WNDPROC in a real session. The PID guard logic also needs a real process-to-window ownership check.

#### 2. Double-Click Foreground Restore (TRAY-02 end-to-end)

**Test:** Hide the window (using the X button or via the tray toggle), then double-click the tray icon.
**Expected:** The terminal window reappears and is raised to the foreground — not merely un-hidden behind other windows.
**Why human:** `SetForegroundWindow` can silently fail under Windows focus-steal prevention rules (returns success but does not foreground). The code is correct but real-world effectiveness depends on the calling process's foreground permission at the time of the click, which varies by session state and cannot be tested with mocked ctypes.

#### 3. Live Tooltip Updates While Hidden (TRAY-03 end-to-end)

**Test:** Hide the window. Observe the tooltip by hovering over the tray icon for 2+ monitoring cycles (default ~60 seconds).
**Expected:** The tooltip text changes each cycle to reflect the current utilization % and Last sync timestamp.
**Why human:** The `update()` method is called by the MonitoringThread via an `on_data_update` callback. Verifying that the thread continues calling `update()` after the window is hidden — and that pystray reflects the new title in the OS tooltip — requires a live runtime.

#### 4. "Open Dashboard" Foreground Restore (TRAY-04 end-to-end)

**Test:** Hide the window, right-click the tray icon, select "Open Dashboard".
**Expected:** The terminal window is restored and brought to the foreground.
**Why human:** Same `SetForegroundWindow` caveat as item 2; additionally requires verifying the pystray menu callback fires `_show_console()` correctly in a real Win32 message loop context.

### Gaps Summary

No gaps. All 4 success criteria are verified at the code level. All 4 TRAY requirements are implemented and traceable to specific lines in `ui/tray_manager.py`. 33/33 unit tests pass. The phase goal is structurally complete.

The `human_needed` status reflects 4 items that require a live Windows runtime to confirm end-to-end behavior — specifically the actual Windows message delivery, `SetForegroundWindow` effectiveness under focus-steal prevention, and MonitoringThread-to-tooltip liveness while the window is hidden. These are runtime integration checks, not code defects.

---

_Verified: 2026-05-21T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
