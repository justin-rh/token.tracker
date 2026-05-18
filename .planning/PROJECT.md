# Claude Token Tracker

## Current Milestone: v2.0 Web-Sourced Usage + System Tray

**Goal:** Replace JSONL-based approximations with authoritative usage data pulled from claude.ai via browser cookies, add a color-coded system tray indicator, and surface per-project token breakdowns.

**Target features:**
- Browser cookie extraction (Chrome primary, Firefox/Edge fallback) to authenticate with claude.ai/settings/usage
- Authoritative plan limits + aggregate usage totals from the claude.ai web API
- Hybrid data layer: web totals merged with JSONL per-project folder breakdown
- System tray icon (green <50%, yellow 50-75%, red >75% of plan limit)
- Keep Rich terminal dashboard, updated to use new data sources
- Monthly usage reset on the 1st of each month
- Auto-refresh every 5 minutes

## What This Is

A Windows-compatible terminal dashboard and system tray indicator for Claude Code token usage, forked and adapted from [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor). v1.0 added Windows support and an overage pool layer. v2.0 switches to authoritative usage data from claude.ai and adds a persistent system tray presence.

## Core Value

Know instantly whether you're on included tokens or burning the $500 overage pool — and how fast.

## Requirements

### Validated

- [x] Reads Claude Code session logs from the Windows path — Phase 1 complete (2026-05-08)
- [x] Infers daily token threshold via P90 percentile with cold-start guard (10-session minimum) — Phase 2 complete (2026-05-08)
- [x] Shows clear calibrating / P90 / manual threshold indicator in the dashboard — Phase 2 complete (2026-05-08)
- [x] Displays a clear INCLUDED / OVERAGE indicator for the current period — Phase 3 complete (2026-05-08)
- [x] Shows est. dollar amount spent from the $500 overage pool in the current billing period — Phase 3 complete (2026-05-08)
- [x] Shows percentage of the $500 pool remaining via progress bar — Phase 3 complete (2026-05-08)
- [x] Shows est. burn rate in $/hr and projects when the $500 pool will be exhausted (OVERAGE only) — Phase 3 complete (2026-05-08)
- [x] Pool spend persists across terminal restarts via atomic pool_spend.json cache — Phase 3 complete (2026-05-08)
- [x] Pool size and billing cycle start day are config-editable without code changes — Phase 3 complete (2026-05-08)

### Active

- [ ] Detects whether the session reset model is rolling 5-hour windows or calendar-day

### Out of Scope

- Linux/Mac support — Windows-first for v1; cross-platform path handling deferred
- System tray / status bar widget — terminal dashboard covers the need for v1
- Web UI or browser-based dashboard — out of scope for v1
- Multi-user / team aggregation — single-user local tool
- Notification alerts (email, Slack, etc.) — visual dashboard is sufficient

## Context

- **Reference tool**: [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) — Python package (v3.1.0), uses Rich for terminal UI, reads `~/.claude/projects/` JSONL files, calculates P90 percentile limits, supports Pro/Max5/Max20 plans
- **Platform**: Windows 11 Enterprise — the reference tool has Unix path assumptions (`~/.claude/...`) that need adaptation for `C:\Users\...`
- **Company plan**: Justin is on a company Anthropic plan with an included daily token allocation (exact limit unknown) and a $500 overage pool that silently activates when included tokens are exhausted — no blocked message, no in-product indicator
- **Primary pain**: No visibility into when usage crosses from included → overage; the $500 pool depletes silently
- **Tech stack**: Fork the reference Python repo — keep Rich terminal UI, JSONL reader, P90 calculator, pricing engine; extend with overage pool logic and Windows path fixes

## Constraints

- **Platform**: Windows 11 — paths, terminal rendering, and file handling must work on Windows
- **Data source**: `~/.claude/projects/` JSONL logs — same format as the reference tool; no API access to Anthropic billing data
- **Threshold**: Daily included-token limit is unknown — must be inferred via P90 percentile, not hardcoded
- **Pool size**: $500 overage pool — should be user-configurable in case it changes

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork the reference tool | Avoids rebuilding JSONL reader, P90 calc, Rich UI from scratch; known working core | Validated Phase 1 |
| P90 threshold detection | User doesn't know their exact daily limit; P90 of historical sessions that hit limits is the reference tool's proven approach | Validated Phase 2 |
| $500 pool size is configurable | Pool size could change; hardcoding would require a code change to update | Validated Phase 3 |
| Windows-first scope | User is on Windows; cross-platform adds complexity without benefit for v1 | Validated Phase 1 |
| pool_state_manager mirrors ThresholdManager pattern | Consistent frozen dataclass + factory fn pattern; same test fixtures; same config-read fallback | Validated Phase 3 |
| Burn rate uses current session rate (not historical) | Simpler to compute from in-scope positional params; labeled as "est." to set expectations | Validated Phase 3 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-08 after Phase 3 completion — milestone v1.0 complete*
