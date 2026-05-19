---
status: complete
phase: 03-overage-pool-dashboard
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md]
started: 2026-05-12T00:00:00Z
updated: 2026-05-12T00:06:00Z
---

## Current Test

[testing complete]

## Tests

### 1. INCLUDED/OVERAGE Status Visible at a Glance
expected: Run the monitor (python monitor.py). The dashboard shows a prominent INCLUDED or OVERAGE status label. When usage is below the inferred threshold it appears green (INCLUDED); when above the threshold it appears red/bold (OVERAGE). The status change is immediately visible without reading numbers.
result: pass

### 2. Pool Spend Row with "est." Prefix
expected: The dashboard shows a pool spend row like "🏦 Pool spent: est. $X.XX / $500.00" — cost figures have the "est." prefix, and the denominator matches the configured pool size.
result: issue
reported: "Pool Spend row is no longer showing up"
severity: major

### 3. Pool Progress Bar
expected: Below the spend row, a wide progress bar shows what percentage of the pool has been spent. It starts green when little has been used, turns yellow around 50% spent, and turns red around 80% spent.
result: issue
reported: "This is also missing"
severity: major

### 4. Burn Rate Row in OVERAGE State
expected: When the session is in OVERAGE state, the dashboard shows a burn rate row like "🔥 Pool burn: est. $X.XX/hr — ~Xh Xm remaining". This row is NOT shown during INCLUDED state.
result: issue
reported: "This row is also not appearing"
severity: major

### 5. Pool Spend Persists After Terminal Restart
expected: Note the "est. pool spent" value displayed. Close the terminal and reopen it, then run python monitor.py again. The pool spend figure should be the same (or higher) — it does not reset to $0.00 on restart.
result: skipped
reason: pool spend row not visible, persistence untestable from UI

### 6. Config-Driven Pool Size and Billing Cycle Day
expected: Open ~/.claude-monitor/config.json (or equivalent config file). The pool_size_usd and billing_cycle_start_day fields should be present and editable. Changing pool_size_usd (e.g., to 250) and restarting the monitor should reflect the new value in the "est. $X.XX / $250.00" denominator without any code changes.
result: issue
reported: "This is not present - I do see pool_spend_seed_usd: 357.01, which we were using when attempting to troubleshoot earlier on Friday"
severity: major

## Summary

total: 6
passed: 1
issues: 4
pending: 0
skipped: 1
blocked: 0

## Gaps

- truth: "Dashboard shows pool spend row: 🏦 Pool spent: est. $X.XX / $500.00"
  status: failed
  reason: "User reported: Pool Spend row is no longer showing up"
  severity: major
  test: 2
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "Dashboard shows wide pool progress bar below spend row (green→yellow→red color escalation)"
  status: failed
  reason: "User reported: This is also missing"
  severity: major
  test: 3
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "Dashboard shows 🔥 Pool burn row (est. $/hr + exhaustion estimate) in OVERAGE state"
  status: failed
  reason: "User reported: This row is also not appearing"
  severity: major
  test: 4
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "config.json contains pool_size_usd and billing_cycle_start_day fields editable without code changes"
  status: failed
  reason: "User reported: This is not present - I do see pool_spend_seed_usd: 357.01, which we were using when attempting to troubleshoot earlier on Friday"
  severity: major
  test: 6
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
