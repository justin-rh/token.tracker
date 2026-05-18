---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Web-Sourced Usage + System Tray
status: planning
stopped_at: ~
last_updated: "2026-05-18T00:00:00.000Z"
last_activity: 2026-05-18
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-18)

**Core value:** Know instantly whether you're on included tokens or burning the $500 overage pool — and how fast.
**Current focus:** Milestone v2.0 started — defining requirements and roadmap

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-18 — Milestone v2.0 started

## Accumulated Context

### Decisions

- v1.0 decisions logged in PROJECT.md Key Decisions table
- v2.0: Switch data source from JSONL-only to hybrid (claude.ai web API for totals + JSONL for per-project breakdown)
- v2.0: P90 threshold inference removed — replaced by actual plan limits from claude.ai
- v2.0: pool_state_manager to be replaced or extended with web-sourced usage data
- v2.0: System tray added via pystray + Pillow

### Pending Todos

None.

### Blockers/Concerns

- RESEARCH NEEDED: claude.ai/settings/usage page structure — must determine if it's SSR HTML or JS-rendered with a JSON API underneath. Affects fetch strategy (requests vs Playwright).
- RESEARCH NEEDED: Exact data fields returned — does the API expose per-project breakdown or aggregate only?
- PITFALL: Chrome cookie encryption on Windows uses DPAPI — browser-cookie3 handles this but needs testing on the user's machine.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-05-18T00:00:00.000Z
Stopped at: ~
Resume file: None
