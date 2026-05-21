---
status: partial
phase: 09-tray-window-lifecycle
source: [09-VERIFICATION.md]
started: 2026-05-21T00:00:00Z
updated: 2026-05-21T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. WM_CLOSE hides to tray
expected: Alt+F4 or clicking X on the terminal window hides it to the system tray without terminating the process; tray icon remains visible
result: [pending]

### 2. Double-click restores to foreground
expected: Left-clicking (double-click default action) on the tray icon calls ShowWindow(SW_RESTORE) + SetForegroundWindow and brings the hidden terminal window to the front
result: [pending]

### 3. Live tooltip while hidden
expected: MonitoringThread continues calling update() and the tray icon tooltip reflects updated utilization % while the terminal window is hidden
result: [pending]

### 4. "Open Dashboard" foreground
expected: Right-click → "Open Dashboard" fires _show_console() which calls ShowWindow(SW_RESTORE) + SetForegroundWindow; hidden window comes to the foreground
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
