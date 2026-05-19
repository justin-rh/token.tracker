---
status: complete
phase: 04-web-data-foundation
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md, 04-06-SUMMARY.md]
started: 2026-05-19T00:00:00Z
updated: 2026-05-19T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running token-tracker process. Start the monitor fresh from the terminal (run: token-tracker). The app should boot, perform auth resolution, and either launch the live dashboard or present the sessionKey prompt — with no crash, traceback, or unhandled exception on startup.
result: pass
note: "ModuleNotFoundError fixed by adding py-modules = ['monitor'] to [tool.setuptools] in pyproject.toml and reinstalling"

### 2. Auth Prompt Before Dashboard
expected: On a run where the sessionKey is NOT cached in Windows Credential Manager, the app pauses BEFORE the live Rich display opens and shows a plain-text prompt instructing you to paste the sessionKey from DevTools. The live dashboard does NOT start until after you paste and confirm.
result: skipped
reason: user did not want to clear keyring entry

### 3. Utilization % via claude.ai
expected: With a valid sessionKey stored, run token-tracker. The live dashboard shows a row labeled "Utilization:" with a progress bar and a percentage value, followed by "via claude.ai" in dim text. Example: "🌐 Utilization:   [████░░] 64.3%  via claude.ai".
result: pass

### 4. Reset Countdown
expected: The dashboard shows a "Resets in:" row below Utilization displaying a countdown in hours and minutes — e.g. "⏱ Resets in:  2h 0m". The value is non-zero during an active 5-hour window.
result: pass

### 5. P90 Threshold Rows Suppressed
expected: When web data is visible (Utilization row present), the P90 calibration / threshold rows from Phase 2 do NOT appear. There is no "Calibrating…", "P90 threshold:", or "Manual limit:" row while "via claude.ai" data is live.
result: pass

### 6. Last Web Sync Footer
expected: Below the Utilization/Resets rows, the dashboard shows a dim "🔄 Last web sync: HH:MM:SS" timestamp indicating when the last successful claude.ai poll completed. The time should match local system time.
result: pass
note: "Fixed: last_sync.astimezone() for sync footer (36514bc); _WINDOWS_TO_IANA mapping + astimezone() fallback for clock (4c9d2c5)"

### 7. Web Unavailable Fallback
expected: Start the monitor without a valid sessionKey (press Enter at the auth prompt, or remove the keyring entry). The dashboard falls back to the P90/threshold display mode and the threshold label includes "(est. — web unavailable)" in dim text.
result: skipped
reason: user did not want to clear keyring entry

## Summary

total: 7
passed: 5
issues: 0
pending: 0
skipped: 2
blocked: 0

## Gaps

[none]
