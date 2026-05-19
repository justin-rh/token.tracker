# Requirements: Claude Token Tracker

**Defined:** 2026-05-07
**Core Value:** Know instantly whether you're on included tokens or burning the $500 overage pool — and how fast.

## v1.0 Requirements (Completed 2026-05-08)

### Windows Port

- [x] **PORT-01**: Tool reads Claude Code session logs from `%APPDATA%\.claude\projects\` (Windows AppData path — tilde expansion resolves incorrectly on Windows)
- [x] **PORT-02**: JSONL entries are deduplicated by `requestId` before token counting (without deduplication counts are 100–174x inflated due to streaming placeholder entries)
- [x] **PORT-03**: Cost calculations use `~/.claude/statusline.jsonl → cost.total_cost_usd` as the primary cost source (raw `costUSD` field was removed in upstream v1.0.9)
- [x] **PORT-04**: Terminal dashboard renders correctly in Windows Terminal (explicit console width argument, VTP enabled, UTF-8 safe — avoids 80-column fallback and encoding errors)

### Threshold Detection

- [x] **THRS-01**: Tool infers the daily included-token limit automatically via P90 percentile of historical sessions that hit rate limits (user does not need to know the exact number)
- [x] **THRS-02**: Cold-start guard displays "Calibrating (N/10 sessions)" until at least 10 sessions of history exist; overage detection does not activate until the threshold is statistically reliable
- [x] **THRS-03**: User can manually set the included-token threshold via config to override P90 detection (for cases where the exact limit is disclosed by the account admin)

### Overage Pool

- [x] **OVGE-01**: Dashboard displays a prominent `INCLUDED` / `OVERAGE` status indicator showing which side of the daily limit current usage falls on
- [x] **OVGE-02**: Dashboard shows estimated dollars spent from the $500 overage pool accumulated in the current billing month
- [x] **OVGE-03**: Dashboard shows percentage of the $500 pool remaining as a visual progress bar
- [x] **OVGE-04**: Dashboard shows $/hr burn rate and projected time until the $500 pool is exhausted at current rate
- [x] **OVGE-05**: Pool spend state persists to a local file across dashboard restarts — closing the terminal does not reset the accumulated overage total
- [x] **OVGE-06**: Pool size (default $500) and billing cycle start date are user-configurable via settings

### Display

- [x] **DISP-01**: Live-updating terminal dashboard with configurable refresh rate (inheriting the reference tool's 0.1–20 Hz range)
- [x] **DISP-02**: All cost figures are prefixed with "est." in the UI to communicate they are estimates derived from local log data, not authoritative billing figures

## v2.0 Requirements

### Cookie Authentication

- [ ] **AUTH-01**: Tool automatically extracts the sessionKey cookie from Firefox (primary) or Chrome/Edge (best-effort — may fail on v127+ due to App-Bound Encryption) to authenticate with claude.ai without user intervention
- [ ] **AUTH-02**: When auto-extraction fails, user can paste a sessionKey value copied from DevTools; the key is stored in Windows Credential Manager via `keyring` and is NOT written to plaintext config files
- [ ] **AUTH-03**: Stored sessionKey persists across restarts; user is not re-prompted on each launch if a valid key already exists in Credential Manager

### Web Data

- [ ] **WEBD-01**: Dashboard displays authoritative 5-hour window utilization % sourced from the claude.ai API, labeled "via claude.ai", replacing the P90-inferred INCLUDED/OVERAGE indicator when web data is available
- [ ] **WEBD-02**: Dashboard displays time remaining until the current 5-hour usage window resets, sourced from claude.ai
- [ ] **WEBD-03**: When web data is unavailable (fetch failure, Cloudflare block, or not yet configured), dashboard falls back to JSONL-based estimates labeled "(est. — web unavailable)"; no crash, no blank display, no user action required

### System Tray

- [ ] **TRAY-01**: A persistent system tray icon is visible while the app is running; icon color reflects 5-hour window utilization — green (<50%), yellow (50–75%), red (>75%)
- [ ] **TRAY-02**: Hovering over the tray icon shows a tooltip with the current utilization % and the last web sync time
- [ ] **TRAY-03**: Right-clicking the tray icon shows a context menu with "Open Dashboard" and "Quit"; selecting Quit triggers clean shutdown identical to Ctrl+C
- [ ] **TRAY-04**: Left-clicking the tray icon toggles the terminal dashboard window between visible and minimized states
- [ ] **TRAY-05**: The tray icon is removed cleanly when the app exits — no ghost icons remain in the notification area

### Polling & Reset

- [ ] **POLL-01**: A background WebPoller thread re-fetches claude.ai usage data every 5 minutes using `threading.Event` (not `time.sleep`); the terminal dashboard displays "Last web sync: HH:MM:SS" after each successful fetch; polling never blocks the display
- [ ] **POLL-02**: Accumulated pool spend resets to $0.00 at the start of the configured billing cycle; the reset event is logged to the console; billing cycle start day remains user-configurable in config without code changes

### Per-Project Breakdown

- [x] **PROJ-01**: Terminal dashboard shows which project folders consumed the most tokens today (current UTC calendar day), sourced from JSONL with "est." prefix
- [x] **PROJ-02**: Terminal dashboard shows which project folders consumed the most tokens this billing month, sourced from JSONL with "est." prefix
- [x] **PROJ-03**: Per-project token data is sourced exclusively from local JSONL files and is never merged with, replaced by, or attributed to web data

## Future Requirements

### Analytics (v2.1+)

- **ANLX-01**: Historical chart of daily pool spend over the billing month
- **ANLX-02**: Overage pool balance from web API (if Anthropic exposes it in a stable endpoint)

### Alerts (v2.1+)

- **ALRT-01**: Terminal bell + color change when pool reaches a user-configured percentage threshold (e.g., 80% exhausted)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Linux / Mac support | Windows-first for v1 and v2; cross-platform adds complexity without benefit to this user |
| Web UI / browser dashboard | Terminal dashboard + system tray covers the visibility need |
| Email / Slack / push notifications | Visual dashboard is the interaction model for v1/v2 |
| Multi-user / team aggregation | Single-user local tool; team reporting requires backend infrastructure |
| Overage pool balance from web API | claude.ai usage endpoint returns utilization % only — pool balance not exposed; JSONL accumulation remains the source |
| Historical monthly spend chart | Deferred to v2.1 analytics milestone |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PORT-01 | Phase 1 — Windows Foundation | Complete |
| PORT-02 | Phase 1 — Windows Foundation | Complete |
| PORT-03 | Phase 1 — Windows Foundation | Complete |
| PORT-04 | Phase 1 — Windows Foundation | Complete |
| DISP-01 | Phase 1 — Windows Foundation | Complete |
| THRS-01 | Phase 2 — Threshold Detection | Complete |
| THRS-02 | Phase 2 — Threshold Detection | Complete |
| THRS-03 | Phase 2 — Threshold Detection | Complete |
| OVGE-01 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-02 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-03 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-04 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-05 | Phase 3 — Overage Pool Dashboard | Complete |
| OVGE-06 | Phase 3 — Overage Pool Dashboard | Complete |
| DISP-02 | Phase 3 — Overage Pool Dashboard | Complete |
| AUTH-01 | Phase 4 — Web Data Foundation | Planned |
| AUTH-02 | Phase 4 — Web Data Foundation | Planned |
| AUTH-03 | Phase 4 — Web Data Foundation | Planned |
| WEBD-01 | Phase 4 — Web Data Foundation | Planned |
| WEBD-02 | Phase 4 — Web Data Foundation | Planned |
| WEBD-03 | Phase 4 — Web Data Foundation | Planned |
| POLL-01 | Phase 4 — Web Data Foundation | Planned |
| POLL-02 | Phase 4 — Web Data Foundation | Planned |
| TRAY-01 | Phase 5 — System Tray | Planned |
| TRAY-02 | Phase 5 — System Tray | Planned |
| TRAY-03 | Phase 5 — System Tray | Planned |
| TRAY-04 | Phase 5 — System Tray | Planned |
| TRAY-05 | Phase 5 — System Tray | Planned |
| PROJ-01 | Phase 6 — Per-Project Breakdown | Complete |
| PROJ-02 | Phase 6 — Per-Project Breakdown | Complete |
| PROJ-03 | Phase 6 — Per-Project Breakdown | Complete |

**Coverage:**
- v1.0 requirements: 15 total — all complete
- v2.0 requirements: 15 total — 13 complete, 2 planned (AUTH-01/02/03 not yet verified as complete in REQUIREMENTS.md)
- Unmapped: 0

---
*Requirements defined: 2026-05-07*
*Last updated: 2026-05-18 — v2.0 traceability updated with phase names*
