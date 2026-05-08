---
phase: 03-overage-pool-dashboard
plan: "03"
subsystem: ui
tags: [pool-dashboard, session-display, rich-ui, progress-bar, burn-rate]
dependency_graph:
  requires:
    - core/pool_state_manager.py (Plan 03-01 — PoolState dataclass)
    - pool_state kwarg in session_display **kwargs (Plan 03-02 — pipeline wiring)
  provides:
    - Pool spend row in active-session dashboard
    - Pool % remaining Rich progress bar
    - Burn rate + exhaustion row (OVERAGE state only)
  affects:
    - ui/session_display.py (visual output of Phase 3)
tech_stack:
  added: []
  patterns:
    - kwargs.get() read pattern for display extensions (mirrors threshold_state Phase 2)
    - _render_wide_progress_bar(pool_pct_spent) — spend% not remaining% for correct color escalation
    - positional params (session_cost, elapsed_session_minutes) used directly for burn rate — no kwargs lookup needed
key_files:
  created: []
  modified:
    - ui/session_display.py
decisions:
  - Pool rows placed OUTSIDE if-threshold_state block but INSIDE if-plan-in-custom branch — reads threshold_state (already in scope) for calibration gate without nesting
  - pool_pct_spent passed to _render_wide_progress_bar (not remaining) — color escalates green→yellow→red as pool depletes (matches D-14)
  - burn_rate_per_hr guarded with if-elapsed_session_minutes>0 first, then if-burn_rate_per_hr>0 before exhaustion — two-level division-by-zero guard (T-03-09)
  - All dollar values carry inline "est." prefix — DISP-02 / T-03-10
metrics:
  duration: "~1 min"
  completed: "2026-05-08"
  tasks_completed: 1
  tasks_total: 2
  files_created: 0
  files_modified: 1
requirements:
  - OVGE-01
  - OVGE-02
  - OVGE-03
  - OVGE-04
  - DISP-02
---

# Phase 03 Plan 03: Pool Dashboard Rendering Summary

**One-liner:** 42-line pool dashboard block inserted into session_display.py — spend row with "est." prefix, progress bar using pool_pct_spent for correct color escalation, and OVERAGE-gated burn rate row with division-by-zero guard.

## What Was Built

`ui/session_display.py` — 42 lines inserted after line 312 (end of Phase 2 threshold block), inside the `if plan in ["custom", "pro", "max5", "max20"]:` branch:

**Pool spend row (always shown when threshold known):**
```
🏦 Pool spent:   est. $X.XX / $500.00
```

**Progress bar row (always shown when threshold known):**
```
   🟢 [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 100.0% remaining
```
Passes `pool_state.pool_pct_spent` (spend %, not remaining %) to `_render_wide_progress_bar` — green < 50% spent, yellow < 80% spent, red >= 80% spent.

**Burn rate row (OVERAGE state only):**
```
🔥 Pool burn:    est. $X.XX/hr — ~Xh Xm remaining
```
Guarded: `if elapsed_session_minutes > 0` before computing rate; `if burn_rate_per_hr > 0` before computing exhaustion. Zero rate shows `—`.

**Display gate:** Pool rows only render when:
1. `pool_state is not None` (non-custom plans pass None through the pipeline)
2. `threshold_state is not None` (calibration state check requires threshold_state in scope)
3. `threshold_state.status != "calibrating"` (suppresses rows during cold-start calibration period)

## Tasks Completed

| Task | Type | Description | Commit |
|------|------|-------------|--------|
| 1 | auto | Insert pool dashboard rows block in session_display.py after Phase 2 threshold block | f125d49 |
| 2 | checkpoint:human-verify | Visual verification of pool dashboard in live terminal | PENDING |

## Acceptance Criteria Verified (Task 1)

- [x] `grep "Pool spent" ui/session_display.py` — match found, contains "est."
- [x] `grep "pool_pct_spent" ui/session_display.py` — 2 matches (correct color direction — spend pct, not remaining)
- [x] `grep "Pool burn" ui/session_display.py` — match found, contains "est."
- [x] `grep "burn_rate_per_hr > 0" ui/session_display.py` — match found (division-by-zero guard)
- [x] `grep "pool_state is not None" ui/session_display.py` — match found
- [x] `grep "status != .calibrating." ui/session_display.py` — match found (calibration gate)
- [x] `python -m pytest tests/ -v` — 31 passed, 0 failed
- [x] `python -c "from ui.session_display import SessionDisplayComponent; print('OK')"` — exits 0

## Deviations from Plan

None — plan executed exactly as written. The code block matches the plan's `<action>` block verbatim.

## Known Stubs

None. The pool rows render real PoolState data computed from actual billing-period block history. No hardcoded placeholder values.

## Threat Surface Scan

No new network endpoints, auth paths, file I/O, or trust boundary changes introduced. The display layer performs arithmetic only on in-process data:
- T-03-09 (DoS via division): Mitigated — `if elapsed_session_minutes > 0` before rate calculation; `if burn_rate_per_hr > 0` before exhaustion. Zero shows "—", no crash.
- T-03-10 (Info Disclosure — "est." prefix): Mitigated — all dollar values in pool rows carry inline "est." prefix (spend row and burn rate row).
- T-03-11 (Tampering — color direction): Mitigated — `pool_state.pool_pct_spent` used directly; code comment documents the spend-not-remaining requirement explicitly.

## Self-Check: PASSED

Files verified:
- FOUND: C:/Users/justin.rhoda/token.tracker/ui/session_display.py (pool rows at lines 314–354)

Commits verified:
- FOUND: f125d49 (feat(03-03): insert pool dashboard rows in session_display.py)

Tests: 31 passed, 0 failed
