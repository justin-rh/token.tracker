# Requirements: Claude Token Tracker

**Defined:** 2026-05-07
**Core Value:** Know instantly whether you're on included tokens or burning the $500 overage pool — and how fast.

## v1 Requirements

### Windows Port

- [ ] **PORT-01**: Tool reads Claude Code session logs from `%APPDATA%\.claude\projects\` (Windows AppData path — tilde expansion resolves incorrectly on Windows)
- [ ] **PORT-02**: JSONL entries are deduplicated by `requestId` before token counting (without deduplication counts are 100–174x inflated due to streaming placeholder entries)
- [ ] **PORT-03**: Cost calculations use `~/.claude/statusline.jsonl → cost.total_cost_usd` as the primary cost source (raw `costUSD` field was removed in upstream v1.0.9)
- [ ] **PORT-04**: Terminal dashboard renders correctly in Windows Terminal (explicit console width argument, VTP enabled, UTF-8 safe — avoids 80-column fallback and encoding errors)

### Threshold Detection

- [ ] **THRS-01**: Tool infers the daily included-token limit automatically via P90 percentile of historical sessions that hit rate limits (user does not need to know the exact number)
- [ ] **THRS-02**: Cold-start guard displays "Calibrating (N/10 sessions)" until at least 10 sessions of history exist; overage detection does not activate until the threshold is statistically reliable
- [ ] **THRS-03**: User can manually set the included-token threshold via config to override P90 detection (for cases where the exact limit is disclosed by the account admin)

### Overage Pool

- [x] **OVGE-01**: Dashboard displays a prominent `INCLUDED` / `OVERAGE` status indicator showing which side of the daily limit current usage falls on
- [x] **OVGE-02**: Dashboard shows estimated dollars spent from the $500 overage pool accumulated in the current billing month
- [x] **OVGE-03**: Dashboard shows percentage of the $500 pool remaining as a visual progress bar
- [x] **OVGE-04**: Dashboard shows $/hr burn rate and projected time until the $500 pool is exhausted at current rate
- [ ] **OVGE-05**: Pool spend state persists to a local file across dashboard restarts — closing the terminal does not reset the accumulated overage total
- [ ] **OVGE-06**: Pool size (default $500) and billing cycle start date are user-configurable via settings

### Display

- [ ] **DISP-01**: Live-updating terminal dashboard with configurable refresh rate (inheriting the reference tool's 0.1–20 Hz range)
- [x] **DISP-02**: All cost figures are prefixed with "est." in the UI to communicate they are estimates derived from local log data, not authoritative billing figures

## v2 Requirements

### Billing Integration

- **BILL-01**: Query Anthropic account API for authoritative pool spend figures (when/if a stable endpoint becomes available)
- **BILL-02**: Alert (terminal bell + color change) when pool reaches a user-configured percentage threshold (e.g., 80% exhausted)

### Analytics

- **ANLX-01**: Historical chart of daily pool spend over the billing month
- **ANLX-02**: Per-project breakdown of token usage and estimated cost

## Out of Scope

| Feature | Reason |
|---------|--------|
| Linux / Mac support | Windows-first for v1; cross-platform path handling adds complexity without benefit to this user |
| System tray / status bar widget | Terminal dashboard covers the visibility need; widget framework adds significant complexity |
| Web UI / browser dashboard | Out of scope for v1 — terminal is sufficient |
| Email / Slack / push notifications | Visual dashboard is the interaction model for v1 |
| Multi-user / team aggregation | Single-user local tool; team reporting requires backend infrastructure |
| OAuth API usage | Undocumented endpoint, rate-limits at 30s intervals, violates ToS per research findings |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PORT-01 | Phase 1 — Windows Foundation | In progress (01-01: baseline established; path fix in 01-02) |
| PORT-02 | Phase 1 — Windows Foundation | Pending |
| PORT-03 | Phase 1 — Windows Foundation | Pending |
| PORT-04 | Phase 1 — Windows Foundation | Pending |
| DISP-01 | Phase 1 — Windows Foundation | In progress (01-01: upstream live display infrastructure present) |
| THRS-01 | Phase 2 — Threshold Detection | In progress (02-01: get_threshold() implemented; 02-02: wired into orchestrator monitoring_data) |
| THRS-02 | Phase 2 — Threshold Detection | In progress (02-01: calibrating status in ThresholdState; 02-02: token_limit=DEFAULT during calibration in orchestrator) |
| THRS-03 | Phase 2 — Threshold Detection | In progress (02-01: manual override via config.json; 02-02: threshold_state passed to monitoring_data) |
| OVGE-01 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-02 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-03 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-04 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-05 | Phase 3 — Overage Pool Dashboard | Pending |
| OVGE-06 | Phase 3 — Overage Pool Dashboard | Pending |
| DISP-02 | Phase 3 — Overage Pool Dashboard | Complete |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-07*
*Last updated: 2026-05-07 after roadmap creation*
