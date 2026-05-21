# Phase 9: Tray Window Lifecycle — Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Intercept the terminal window close event (X button / Alt+F4) so the app hides to the system tray instead of terminating. The tray icon already exists (Phase 5) and already has hide/show methods — the missing piece is `WM_CLOSE` interception. Tray double-click and "Open Dashboard" menu item must restore and foreground the window.

Out of scope: any new tray menu items beyond those in Phase 5, config file changes, non-Windows platforms, notification balloons.

</domain>

<decisions>
## Implementation Decisions

### WM_CLOSE Interception
- **D-01:** Use `SetWindowLongPtr(hwnd, GWLP_WNDPROC, ...)` to subclass the console window procedure. When `WM_CLOSE` is received, call `ShowWindow(hwnd, SW_HIDE)` and return 0 — do NOT call `DefWindowProc`, which would destroy the window. This is the Windows-standard, reliable approach.
- **D-02:** The subclassed WNDPROC must be a `ctypes.WINFUNCTYPE` callback stored as an instance attribute (to prevent garbage collection). The original WNDPROC must be saved and restored on app exit to avoid memory leaks / crashes on cleanup.
- **D-03:** WM_CLOSE interception lives in `TrayManager` — it already owns all ctypes window manipulation. Wire it up in `start()` after `run_detached()` confirms the icon is running.

### Shell vs Standalone Detection
- **D-04:** Before subclassing, compare the console window's owning process ID to `os.getpid()`:
  ```python
  pid = ctypes.c_ulong()
  ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
  owns_console = (pid.value == os.getpid())
  ```
  If `owns_console` is False (shell context — PowerShell/cmd owns the window), skip WM_CLOSE interception entirely and log an INFO message. App behaves normally (X closes the process) in shell context. No user-facing warning needed.

### Restore / Focus Behavior
- **D-05:** When restoring the window from tray (double-click or "Open Dashboard"), call both `ShowWindow(hwnd, SW_RESTORE)` AND `SetForegroundWindow(hwnd)`. User clicked the tray intentionally — the window should come to front.
- **D-06:** Update `_show_console()` and `_toggle_console()` in `TrayManager` to add `SetForegroundWindow` after the existing `ShowWindow` call.

### Close = Hide (No Prompt)
- **D-07:** X button / Alt+F4 always hides to tray silently. No balloon notification, no prompt. The only way to fully quit is via the tray "Quit" menu item. Consistent with standard Windows tray-app behavior (Slack, Discord pattern).

### Cleanup on Exit
- **D-08:** In `TrayManager.stop()`, restore the original WNDPROC via `SetWindowLongPtr(hwnd, GWLP_WNDPROC, original_wndproc)` before calling `icon.stop()`. This ensures clean process exit without leaving a dangling hook.

### Claude's Discretion
- Whether to put the WNDPROC setup in a separate `_install_close_guard()` private method or inline in `start()`.
- Whether to re-show the window on startup if it was hidden when the previous session exited (not required by any requirement — only if trivially achievable).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — TRAY-01, TRAY-02, TRAY-03, TRAY-04 acceptance criteria
- `.planning/ROADMAP.md` §Phase 9 — success criteria and phase goal

### Implementation Files (read before editing)
- `ui/tray_manager.py` — ALL tray changes go here; `_toggle_console()`, `_show_console()` already use `GetConsoleWindow()` + `ShowWindow`; `SW_HIDE = 0`, `SW_RESTORE = 9` already defined
- `cli/main.py` — TrayManager lifecycle (start at line ~206, stop at line ~298); do NOT change the lifecycle wiring

### Architecture Notes (from STATE.md)
- `GetConsoleWindow()` returns outer shell HWND when launched inside PowerShell/cmd — D-04 detection handles this
- `icon.run_detached()` is called from main thread (not a 4th thread) — WNDPROC subclassing must also happen from main thread or be thread-safe

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ui/tray_manager.py` — `_toggle_console()` already has `GetConsoleWindow()` + `IsWindowVisible()` + `ShowWindow()` pattern. WNDPROC subclassing extends this same ctypes block.
- `SW_HIDE = 0`, `SW_RESTORE = 9` module constants already defined — reuse them.
- `ctypes.windll.user32` and `ctypes.windll.kernel32` already imported.

### Integration Points
- `TrayManager.start()` — add `_install_close_guard()` call after `run_detached()`
- `TrayManager.stop()` — add WNDPROC restore before `icon.stop()`
- `TrayManager._show_console()` and `_toggle_console()` — add `SetForegroundWindow` after `ShowWindow`

### What Is NOT Needed
- No changes to `cli/main.py` — lifecycle wiring is complete
- No changes to `monitoring/orchestrator.py`
- No new config keys

</code_context>

<specifics>
## Specific Ideas

- `WINFUNCTYPE(c_long, HWND, UINT, WPARAM, LPARAM)` is the WNDPROC signature. The callback must be stored as `self._wndproc_cb` (instance attribute) to prevent CPython garbage collection.
- `SetWindowLongPtr` is the 64-bit-safe version (use over `SetWindowLong`). On 32-bit Python, they are the same but `SetWindowLongPtr` is always correct.
- `WM_CLOSE = 0x0010` — the message to intercept.
- `GWLP_WNDPROC = -4` — the index for `SetWindowLongPtr` to replace the window procedure.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-tray-window-lifecycle*
*Context gathered: 2026-05-20*
