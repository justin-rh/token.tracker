# Roadmap: Claude Token Tracker

## Overview

Fork the Claude-Code-Usage-Monitor Python tool, port it to Windows, wire up P90 threshold detection, then layer on the overage pool dashboard that answers the only question that matters: "Am I burning the $500 pool — and how fast?"

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Windows Foundation** - Fork and run the tool correctly on Windows with accurate data
- [ ] **Phase 2: Threshold Detection** - Infer the daily included-token limit via P90 with cold-start guard
- [ ] **Phase 3: Overage Pool Dashboard** - Display included/overage status, pool spend, burn rate, and projections

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
**Plans**: 5 plans

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
**Plans**: 3 plans

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
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Windows Foundation | 5/5 | Complete | 2026-05-08 |
| 2. Threshold Detection | 3/3 | Complete | 2026-05-08 |
| 3. Overage Pool Dashboard | 0/TBD | Not started | - |
