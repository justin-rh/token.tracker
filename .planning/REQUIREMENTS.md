# Requirements — v2.1 Polish + Analytics

## Milestone Goal

Fix the system tray window lifecycle, surface historical spend data, and clean up accuracy/quality issues carried forward from v2.0.

---

## Active Requirements

### Tray Window Lifecycle

- [ ] **TRAY-01**: User can close the terminal window and the app continues running in the system tray
- [ ] **TRAY-02**: User can double-click the tray icon to restore the terminal window
- [ ] **TRAY-03**: Tray icon tooltip continues showing current utilization % while window is hidden
- [ ] **TRAY-04**: "Open Dashboard" right-click menu item restores the window when it is hidden

### Historical Analytics

- [ ] **ANLX-01**: User can see a chart of daily pool spend for the current billing cycle inline in the terminal dashboard
- [ ] **ANLX-02**: Each bar shows date label and spend amount; current day is visually distinguished
- [ ] **ANLX-03**: Chart is only shown when at least one day of pool spend data exists

### Burn Rate Accuracy

- [ ] **BURN-01**: Pool burn rate ($/hr) is derived from the rate of change of `pool_spend_usd` over a rolling time window rather than current-session cost/elapsed-time
- [ ] **BURN-02**: Burn rate row is hidden (not shown as $0.00) when insufficient history exists to compute a meaningful rate

### Code Quality

- [ ] **QUAL-01**: Test suite handles sessions spanning midnight without date-skew failures (WR-01)
- [ ] **QUAL-02**: When two projects share a display name, a WARNING is logged identifying the collision (WR-02)
- [ ] **QUAL-03**: Billing cycle start comparisons use UTC-normalized datetimes consistently throughout (WR-03)
- [ ] **QUAL-04**: Per-project row padding uses `_col_pad()` for all f-string segments containing Rich markup (WR-04)

---

## Future Requirements

- Terminal bell / desktop notification at configurable pool % threshold (ALRT-01) — deferred to v2.2+
- Historical monthly spend chart beyond current billing cycle — deferred to v2.2+

---

## Out of Scope

- Linux/Mac support — Windows-first
- Web UI or browser-based dashboard — terminal + tray covers the need
- Email/Slack/push notifications — visual dashboard is the interaction model
- Multi-user / team aggregation — single-user local tool
- Overage pool balance from web API — utilization % only; JSONL accumulation remains the source

---

## Traceability

| REQ-ID  | Phase | Plan |
|---------|-------|------|
| TRAY-01 | TBD   | TBD  |
| TRAY-02 | TBD   | TBD  |
| TRAY-03 | TBD   | TBD  |
| TRAY-04 | TBD   | TBD  |
| ANLX-01 | TBD   | TBD  |
| ANLX-02 | TBD   | TBD  |
| ANLX-03 | TBD   | TBD  |
| BURN-01 | TBD   | TBD  |
| BURN-02 | TBD   | TBD  |
| QUAL-01 | TBD   | TBD  |
| QUAL-02 | TBD   | TBD  |
| QUAL-03 | TBD   | TBD  |
| QUAL-04 | TBD   | TBD  |
