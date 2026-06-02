# Roadmap: Claude Token Tracker

## Milestones

- ✅ **v1.0 Windows Foundation + Overage Pool** — Phases 1–3 (shipped 2026-05-08)
- ✅ **v2.0 Web-Sourced Usage + System Tray** — Phases 4–6 (shipped 2026-05-19)
- ✅ **v2.1 Polish + Analytics** — Phases 7–10 (shipped 2026-06-02)

## Phases

<details>
<summary>✅ v1.0 Windows Foundation + Overage Pool (Phases 1–3) — SHIPPED 2026-05-08</summary>

- [x] Phase 1: Windows Foundation (5/5 plans) — completed 2026-05-08
- [x] Phase 2: Threshold Detection (3/3 plans) — completed 2026-05-08
- [x] Phase 3: Overage Pool Dashboard (3/3 plans) — completed 2026-05-08

</details>

<details>
<summary>✅ v2.0 Web-Sourced Usage + System Tray (Phases 4–6) — SHIPPED 2026-05-19</summary>

- [x] Phase 4: Web Data Foundation (6/6 plans) — completed 2026-05-19
- [x] Phase 5: System Tray (2/2 plans) — completed 2026-05-19
- [x] Phase 6: Per-Project Breakdown (4/4 plans) — completed 2026-05-19

</details>

### v2.1 Polish + Analytics

**Milestone Goal:** Fix system tray window lifecycle, surface historical spend analytics, improve burn rate accuracy, and resolve four carried-forward code quality issues.

- [x] **Phase 7: Code Quality** — Four isolated correctness fixes with no cross-module dependencies — completed 2026-05-20
- [x] **Phase 8: Burn Rate Accuracy** — Derive $/hr from pool_spend_usd delta over a rolling time window — completed 2026-05-20
- [x] **Phase 9: Tray Window Lifecycle** — Window hides on close; tray icon restores it on double-click or menu — completed 2026-05-21
- [x] **Phase 10: Historical Analytics** — Daily pool spend bar chart rendered inline in the terminal dashboard — completed 2026-06-02

## Phase Details

### Phase 7: Code Quality
**Goal**: Four isolated correctness issues carried forward from v2.0 code review are resolved, leaving the test suite reliable and the display logic sound
**Depends on**: Phase 6 (v2.0 complete)
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04
**Success Criteria** (what must be TRUE):
  1. Test suite passes without date-skew failures when a session spans midnight
  2. When two projects share a display name, a WARNING log line identifies both paths and the collision
  3. Billing cycle start comparisons use UTC-normalized datetimes and never raise timezone-offset errors
  4. Per-project row columns align correctly in the terminal even when project names contain Rich markup characters
**Plans**: 3 plans

Plans:
- [x] 07-01-PLAN.md — Add today param to _derive_billing_cycle_start + compute_pool_state; update tests (WR-01, WR-03)
- [x] 07-02-PLAN.md — Bump display_name collision log to WARNING with both slugs; add collision test (WR-02)
- [x] 07-03-PLAN.md — Add _col_pad unit tests + human spot-check checkpoint (WR-04)

### Phase 8: Burn Rate Accuracy
**Goal**: Pool burn rate shown in the dashboard reflects actual pool_spend_usd velocity over a rolling window rather than current-session cost divided by elapsed time
**Depends on**: Phase 7
**Requirements**: BURN-01, BURN-02
**Success Criteria** (what must be TRUE):
  1. The $/hr figure in the dashboard changes only when pool_spend_usd changes, not when session cost or uptime changes
  2. The burn rate row is absent from the display when fewer than two pool_spend_usd samples exist in the rolling window
  3. After pool spend accumulates across multiple monitoring cycles the burn rate stabilizes to a credible $/hr figure
**Plans**: 2 plans

Plans:
- [x] 08-01-PLAN.md — Add ring buffer state to orchestrator; compute pool_burn_rate_usd_per_hr in _fetch_and_process_data (BURN-01, BURN-02)
- [x] 08-02-PLAN.md — Replace inline formula in session_display.py with kwargs read; add test_burn_rate.py (BURN-01, BURN-02)

### Phase 9: Tray Window Lifecycle
**Goal**: Users can close the terminal window to minimize the app to the tray, and restore it from the tray without restarting the process
**Depends on**: Phase 7
**Requirements**: TRAY-01, TRAY-02, TRAY-03, TRAY-04
**Success Criteria** (what must be TRUE):
  1. Closing the terminal window hides it rather than terminating the process; the tray icon remains visible
  2. Double-clicking the tray icon brings the hidden window back to the foreground
  3. The tray icon tooltip continues updating with current utilization % while the window is hidden
  4. Selecting "Open Dashboard" from the tray right-click menu restores a hidden window to the foreground
**Plans**: 2 plans

Plans:
- [x] 09-01-PLAN.md — Add _install_close_guard() with WNDPROC subclassing, PID guard, start()/stop() wiring (TRAY-01, TRAY-03)
- [x] 09-02-PLAN.md — Add SetForegroundWindow to _show_console() and _toggle_console(); add TestCloseGuard tests (TRAY-02, TRAY-03, TRAY-04)

### Phase 10: Historical Analytics
**Goal**: Users can see how pool spend has trended day-by-day across the current billing cycle without leaving the terminal dashboard
**Depends on**: Phase 8
**Requirements**: ANLX-01, ANLX-02, ANLX-03
**Success Criteria** (what must be TRUE):
  1. A bar chart of daily pool spend for the current billing cycle appears inline in the terminal dashboard
  2. Each bar is labeled with its date and spend amount; the current day's bar is visually distinct from prior days
  3. The chart section is hidden entirely when no pool spend data yet exists for the billing cycle
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Windows Foundation | v1.0 | 5/5 | Complete | 2026-05-08 |
| 2. Threshold Detection | v1.0 | 3/3 | Complete | 2026-05-08 |
| 3. Overage Pool Dashboard | v1.0 | 3/3 | Complete | 2026-05-08 |
| 4. Web Data Foundation | v2.0 | 6/6 | Complete | 2026-05-19 |
| 5. System Tray | v2.0 | 2/2 | Complete | 2026-05-19 |
| 6. Per-Project Breakdown | v2.0 | 4/4 | Complete | 2026-05-19 |
| 7. Code Quality | v2.1 | 3/3 | Complete | 2026-05-20 |
| 8. Burn Rate Accuracy | v2.1 | 2/2 | Complete | 2026-05-20 |
| 9. Tray Window Lifecycle | v2.1 | 2/2 | Complete | 2026-05-21 |
| 10. Historical Analytics | v2.1 | 2/2 | Complete | 2026-06-02 |

Archive: `.planning/milestones/v2.0-ROADMAP.md`
