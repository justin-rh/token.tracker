# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-07)

**Core value:** Know instantly whether you're on included tokens or burning the $500 overage pool — and how fast.
**Current focus:** Phase 1 — Windows Foundation

## Current Position

Phase: 1 of 3 (Windows Foundation)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-05-07 — Roadmap created

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Fork reference tool (not install): avoids patching site-packages, enables direct source edits
- P90 threshold detection: user doesn't know exact included-token limit; infer from session history
- $500 pool size is config-driven: hardcoding would require code change if pool changes
- Windows-first scope: cross-platform adds complexity without benefit for v1

### Pending Todos

None yet.

### Blockers/Concerns

- PITFALL: Windows AppData path — Claude Code logs are in `%APPDATA%\.claude\projects\`, not `~\.claude\projects\`. Must verify empirically on first run (Phase 1).
- PITFALL: WinError 32 file sharing — active session JSONL is held open by Claude Code. Wrap reads in try/except PermissionError.
- PITFALL: requestId deduplication — must verify upstream fork preserves this logic; without it token counts are 100-174x inflated.
- RESEARCH FLAG: Pool accumulation period (monthly vs billing-cycle) — architecture assumes calendar-month; verify with account owner before Phase 3.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-05-07
Stopped at: Roadmap created — ready to plan Phase 1
Resume file: None
