# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-07)

**Core value:** Know instantly whether you're on included tokens or burning the $500 overage pool — and how fast.
**Current focus:** Phase 1 — Windows Foundation

## Current Position

Phase: 1 of 3 (Windows Foundation)
Plan: 3 of 5 in current phase
Status: Executing
Last activity: 2026-05-08 — Completed 01-03 (requestId Deduplication)

Progress: [███░░░░░░░] 6%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 4.3 min
- Total execution time: 0.2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-windows-foundation | 3/5 | 15 min | 5 min |

**Recent Trend:**
- Last 5 plans: 01-01, 01-02, 01-03
- Trend: On track

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Fork reference tool (not install): avoids patching site-packages, enables direct source edits
- P90 threshold detection: user doesn't know exact included-token limit; infer from session history
- $500 pool size is config-driven: hardcoding would require code change if pool changes
- Windows-first scope: cross-platform adds complexity without benefit for v1
- [01-01] claude_monitor/ shim package: aliases flat repo-root modules under claude_monitor.* namespace — avoids patching 40+ source files
- [01-01] monitor.py delegates to cli.main:main(): upstream CLI parser unchanged; Windows UTF-8 + VTP setup first
- [01-01] Windows VTP enabled via ctypes in monitor.py: ANSI colors work in cmd.exe
- [01-02] Use os.environ["APPDATA"] not Path.home(): APPDATA resolves AppData/Roaming; home() resolves USERPROFILE root (wrong location)
- [01-02] LOCKED_FILES as module-level list: avoids changing load_usage_entries return type; UI reads data.reader.LOCKED_FILES after each call
- [01-02] utf-8-sig + newline='' on all JSONL opens: handles BOM and CRLF line endings without parse errors
- [01-03] Collect all raw JSONL lines per file first, then deduplicate, then map — ensures max(output_tokens) selection works across full set of streaming chunks
- [01-03] Existing _create_unique_hash() / processed_hashes dedup left in place as secondary guard against cross-file message_id duplicates (different concern)

### Pending Todos

None yet.

### Blockers/Concerns

- PITFALL: Windows AppData path — Claude Code logs are in `%APPDATA%\.claude\projects\`, not `~\.claude\projects\`. Must verify empirically on first run (Phase 1).
- PITFALL: WinError 32 file sharing — active session JSONL is held open by Claude Code. Wrap reads in try/except PermissionError.
- PITFALL: requestId deduplication — RESOLVED in 01-03: _deduplicate_entries() added, max(output_tokens) per requestId, all 5 unit tests pass.
- RESEARCH FLAG: Pool accumulation period (monthly vs billing-cycle) — architecture assumes calendar-month; verify with account owner before Phase 3.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-05-08
Stopped at: Completed 01-03-PLAN.md — ready to execute 01-04
Resume file: None
