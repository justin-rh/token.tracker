# Roadmap: Claude Token Tracker

## Overview

Fork the Claude-Code-Usage-Monitor Python tool, port it to Windows, wire up P90 threshold detection, then layer on the overage pool dashboard that answers the only question that matters: "Am I burning the $500 pool — and how fast?"

v2.0 extends the v1.0 terminal dashboard with authoritative usage data pulled from claude.ai via browser cookie authentication, a persistent color-coded system tray indicator, and per-project token breakdowns. `core/usage_fetcher.py` already exists — AUTH and WEBD extend it, they do not rebuild it. Two net-new modules (`monitoring/web_poller.py`, `ui/tray_manager.py`) cover the new surface area.

## Phase Numbering Note

v1.0 delivered Phases 1–3. v2.0 phases are numbered 4–6, continuing the same sequence.

- Integer phases (1, 2, 3, 4, 5, 6): Planned milestone work
- Decimal phases (4.1, 4.2): Urgent insertions (marked with INSERTED)

## Phases

- [x] **Phase 1: Windows Foundation** - Fork and run the tool correctly on Windows with accurate data (completed 2026-05-08)
- [x] **Phase 2: Threshold Detection** - Infer the daily included-token limit via P90 with cold-start guard (completed 2026-05-08)
- [x] **Phase 3: Overage Pool Dashboard** - Display included/overage status, pool spend, burn rate, and projections (completed 2026-05-08)
- [x] **Phase 4: Web Data Foundation** - Authenticate with claude.ai, fetch authoritative usage data, display it in the terminal dashboard, and poll every 5 minutes (completed 2026-05-19)
- [ ] **Phase 5: System Tray** - Persistent color-coded tray icon driven by web utilization %, with tooltip, right-click menu, left-click toggle, and clean shutdown
- [ ] **Phase 6: Per-Project Breakdown** - Surface which project folders consumed the most tokens today and this billing month, sourced from local JSONL

## Phase Details

### Phase 1: Windows Foundation
**Goal**: The forked tool runs on Windows, reads live Claude Code session logs, deduplicates JSONL correctly, reports accurate cost figures, and renders the Rich dashboard without layout breakage
**Depends on**: Nothing (first phase)
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, DISP-01
**Success Criteria** (what must be TRUE):
  1. Running the tool in Windows Terminal shows session data from `%APPDATA%\.claude\projects\` — no "no data found" with logs present
  2. Token totals match expectations (not 100-174x inflated) — deduplication by requestId is active
  3. Cost figures are sourced from statusline.jsonl `cost.total_cost_usd`, not the removed `costUSD` JSONL field
  4. Dashboard renders at full terminal width in Windows Terminal with no 80-column wrapping or encoding errors
  5. Live display updates at the configured refresh rate without scrolling instead of refreshing in place
**Plans**: 5 plans (complete)

Plans:
- [x] 01-01-PLAN.md — Fork upstream and bootstrap project structure (pyproject.toml, monitor.py entry point)
- [x] 01-02-PLAN.md — Windows path fix (APPDATA) and file-lock handling (PermissionError / WinError 32)
- [x] 01-03-PLAN.md — requestId deduplication with unit tests
- [x] 01-04-PLAN.md — Replace costUSD with statusline.jsonl cost source
- [x] 01-05-PLAN.md — Rich Console width fix, VTP setup, active-session indicator, smoke test checkpoint

### Phase 2: Threshold Detection
**Goal**: The tool automatically infers the daily included-token limit from historical session data, displays a calibration state during cold start, and accepts a manual override when the exact limit is known
**Depends on**: Phase 1
**Requirements**: THRS-01, THRS-02, THRS-03
**Success Criteria** (what must be TRUE):
  1. On first run with fewer than 10 sessions, the dashboard shows "Calibrating (N/10 sessions)" — no false overage warnings trigger
  2. After 10 or more sessions of history, a P90 token threshold is displayed and overage detection activates
  3. Setting `overage_threshold_tokens` in config bypasses P90 and the dashboard shows "threshold: manual" — P90 calibration is skipped
**Plans**: 3 plans (complete)

Plans:
- [x] 02-01-PLAN.md — Create core/threshold_manager.py (ThresholdState dataclass + get_threshold() with full unit tests)
- [x] 02-02-PLAN.md — Wire ThresholdManager into monitoring/orchestrator.py (add threshold_state to monitoring_data)
- [x] 02-03-PLAN.md — Render threshold rows in ui/session_display.py (calibrating/auto/manual + INCLUDED/OVERAGE status)

### Phase 3: Overage Pool Dashboard
**Goal**: Users can see at a glance whether current usage is on included tokens or burning the $500 pool, how much of the pool has been spent, and how long the pool will last at the current burn rate
**Depends on**: Phase 2
**Requirements**: OVGE-01, OVGE-02, OVGE-03, OVGE-04, OVGE-05, OVGE-06, DISP-02
**Success Criteria** (what must be TRUE):
  1. Dashboard shows a prominent INCLUDED or OVERAGE status that changes color dramatically at the boundary — visible at a glance without reading numbers
  2. Dashboard shows est. dollars spent from the $500 pool this billing month as a progress bar with "est." prefix on all cost figures
  3. Dashboard shows $/hr burn rate and projected time until pool exhaustion while in OVERAGE state
  4. Closing and reopening the terminal preserves accumulated pool spend — it does not reset to $0
  5. Pool size (default $500) and billing cycle start date are editable in the config file without code changes
**Plans**: 3 plans (complete)

Plans:
- [x] 03-01-PLAN.md — Create core/pool_state_manager.py (PoolState dataclass + compute_pool_state() + full unit tests)
- [x] 03-02-PLAN.md — Wire pool_state through orchestrator → display_controller → cli/main.py
- [x] 03-03-PLAN.md — Render pool dashboard rows in ui/session_display.py (pool spend, progress bar, burn rate)

### Phase 4: Web Data Foundation
**Goal**: Users see authoritative 5-hour window utilization % and reset time sourced directly from claude.ai, refreshed every 5 minutes in the background, with graceful fallback to JSONL estimates when web data is unavailable
**Depends on**: Phase 3
**Requirements**: AUTH-01, AUTH-02, AUTH-03, WEBD-01, WEBD-02, WEBD-03, POLL-01, POLL-02
**Success Criteria** (what must be TRUE):
  1. On launch, the dashboard displays a 5-hour window utilization % and reset countdown labeled "via claude.ai" — sourced from the web API, not P90 inference
  2. When auto cookie extraction fails (Chrome ABE, no browser), the app prompts once for a manual sessionKey paste; the key is stored in Windows Credential Manager and not re-prompted on subsequent launches
  3. When the web fetch fails for any reason (Cloudflare block, network error, expired session), the dashboard silently falls back to "(est. — web data unavailable)" with no crash and no blank rows
  4. "Last web sync: HH:MM:SS" updates in the dashboard after each successful background fetch, which occurs every 5 minutes without blocking the display
  5. On the configured billing cycle start day, accumulated pool spend resets to $0.00 and a reset event appears in the console log
**Plans**: 6 plans

Plans:
- [x] 04-01-PLAN.md — Add keyring/browser-cookie3/httpx dependencies + WebUsageData frozen dataclass
- [x] 04-02-PLAN.md — usage_fetcher.py: Firefox extraction, keyring migration, _read_auth_cookies() refactor, fetch_web_usage(), _discover_org_id()
- [x] 04-03-PLAN.md — Create monitoring/web_poller.py (WebPoller daemon thread, 300s Event loop, thread-safe cache)
- [x] 04-04-PLAN.md — Orchestrator wire-up (set_web_poller, web_usage in monitoring_data) + display_controller kwarg pass-through
- [x] 04-05-PLAN.md — session_display.py: Utilization/Resets In rows (D-17), web-unavailable fallback (D-18), Last web sync footer (D-19)
- [x] 04-06-PLAN.md — cli/main.py: auth setup flow (D-08/D-09) + WebPoller start/stop + D-24 billing reset log

### Phase 5: System Tray
**Goal**: A persistent tray icon provides at-a-glance utilization status without requiring the terminal window to be visible, with controls to toggle the dashboard and quit cleanly
**Depends on**: Phase 4
**Requirements**: TRAY-01, TRAY-02, TRAY-03, TRAY-04, TRAY-05
**Success Criteria** (what must be TRUE):
  1. A color-coded tray icon appears in the Windows notification area on launch — green when utilization is below 50%, yellow at 50–75%, red above 75%
  2. Hovering over the tray icon shows a tooltip with the current utilization % and the timestamp of the last successful web sync
  3. Right-clicking the tray icon shows a menu with "Open Dashboard" and "Quit"; selecting Quit shuts down the app identically to Ctrl+C — no hung process, no ghost icon
  4. Left-clicking the tray icon toggles the terminal window between visible and minimized without launching a second instance
  5. After the app exits (any path), the tray icon is gone from the notification area — no ghost icons require a hover to clear
**Plans**: TBD
**UI hint**: yes

### Phase 6: Per-Project Breakdown
**Goal**: Users can see which Claude Code project folders consumed the most tokens today and this billing month, giving context for where usage is coming from
**Depends on**: Phase 4
**Requirements**: PROJ-01, PROJ-02, PROJ-03
**Success Criteria** (what must be TRUE):
  1. The terminal dashboard shows a ranked list of project folders by token count for the current UTC calendar day, labeled "est." — sourced from JSONL
  2. The terminal dashboard shows a ranked list of project folders by token count for the current billing month, labeled "est." — sourced from JSONL
  3. Per-project token figures remain unchanged when web data is available — web data never overwrites, augments, or mixes with the JSONL per-project rows
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Windows Foundation | 5/5 | Complete | 2026-05-08 |
| 2. Threshold Detection | 3/3 | Complete | 2026-05-08 |
| 3. Overage Pool Dashboard | 3/3 | Complete | 2026-05-08 |
| 4. Web Data Foundation | 6/6 | Complete | 2026-05-19 |
| 5. System Tray | 0/TBD | Not started | - |
| 6. Per-Project Breakdown | 0/TBD | Not started | - |
