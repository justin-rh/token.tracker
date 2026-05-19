# Phase 2: Threshold Detection - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Infer the daily included-token limit automatically via P90 from historical session data. Display a "Calibrating" state until enough history exists. Accept a persistent manual override via config file. Expose a simple INCLUDED/OVERAGE status signal once threshold is known. No dollar amounts, burn rate, or pool spend in this phase — those are Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Qualifying Sessions for P90 and Cold-Start
- **D-01:** All completed (non-active, non-gap) session blocks feed both the P90 calculation and the cold-start counter. Do NOT filter by "appeared to hit a known limit" — the company plan limit is unknown and the rate-limit filter would fall back to all sessions anyway (see `core/p90_calculator.py:36-43`).
- **D-02:** Cold-start minimum is **10 sessions**, hardcoded. Not configurable. Once 10+ completed blocks exist, P90 activates.

### Config File for Manual Override (THRS-03)
- **D-03:** Manual threshold override is stored in a **new persistent file**: `~/.claude-monitor/config.json`. Key name: `overage_threshold_tokens` (integer, token count). This file is separate from `~/.claude-monitor/last_used.json` (which stores transient CLI params).
- **D-04:** If `overage_threshold_tokens` is present in `config.json`, P90 calibration is **skipped entirely** — do not count sessions, do not calculate P90. Use the configured value directly.

### Calibration Display (THRS-02)
- **D-05:** During cold start (fewer than 10 completed sessions), the threshold row in the dashboard shows:
  `Token limit: Calibrating (N/10 sessions)`
  where N is the current count of completed session blocks.
- **D-06:** No false overage warnings during calibration — the INCLUDED/OVERAGE label is suppressed entirely until threshold is known.
- **D-07:** Once calibration completes (10+ sessions, auto-inferred via P90), the threshold row shows:
  `Token limit: 88,000 tokens (P90)`
  (actual P90 value, not the literal 88,000 — that's just an example).
- **D-08:** When manual override is set, the threshold row shows:
  `Token limit: 88,000 tokens (manual)`
  P90 calibration does not run at all in this state.

### Phase 2 Overage Signal (THRS-01)
- **D-09:** Once the threshold is known (either P90 or manual), add a one-line status label to the dashboard:
  - ✅ INCLUDED — current session tokens are at or below the threshold
  - 🔴 OVERAGE — current session tokens exceed the threshold
  No dollar amounts, no burn rate, no pool spend in Phase 2. Those are Phase 3 territory.
- **D-10:** This status row is the foundation Phase 3 builds on. Place it prominently so Phase 3 can extend it with pool spend data alongside.

### Claude's Discretion
- Exact row label and formatting (Rich markup, emoji vs colored text) — Claude's call. Consistency with the existing Rich dashboard style.
- Whether config.json is read at startup only or polled each refresh cycle.
- Error handling if config.json exists but `overage_threshold_tokens` is malformed (e.g., non-integer) — log a warning and fall back to P90.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 Requirements
- `.planning/REQUIREMENTS.md` — THRS-01, THRS-02, THRS-03 are in scope. Read for exact acceptance criteria.

### Prior Phase Context
- `.planning/phases/01-windows-foundation/01-CONTEXT.md` — D-03 (Windows path), D-05 (WinError 32), D-06/D-07 (cost source) carry forward. The `~/.claude-monitor/` directory (used for config.json) parallels the `last_used.json` path already established.

### Research (Pre-existing)
- `.planning/research/PITFALLS.md` — Windows-specific pitfalls still apply (path handling, file locking).
- `.planning/research/ARCHITECTURE.md` — Component map showing where threshold detection integrates.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/p90_calculator.py` — `P90Calculator.calculate_p90_limit(blocks)` already works. Phase 2 feeds it all completed blocks (not just rate-limit-hit blocks). No changes needed to the calculator itself — only how we call it and how we handle the cold-start case.
- `core/plans.py` — `Plans.get_token_limit("custom", blocks)` already delegates to P90Calculator for the "custom" plan type. The cold-start guard and config.json read should wrap or replace this call path.
- `core/settings.py` — `Settings.custom_limit_tokens` (CLI arg) exists but is NOT the config file mechanism. Keep it for CLI power users; config.json is the persistent override path.
- `monitoring/orchestrator.py:_calculate_token_limit()` — This is the entry point where the new threshold logic (cold-start check + config.json read + P90 call) should live.

### Established Patterns
- `~/.claude-monitor/last_used.json` — written by `core/settings.py:LastUsedParams`. `config.json` goes in the same directory (`~/.claude-monitor/`).
- Rich dashboard rows follow a consistent label + value pattern in `ui/session_display.py` and `ui/components.py`. The "Token limit" row is the one to modify.

### Integration Points
- `monitoring/orchestrator.py:_calculate_token_limit()` — add cold-start check + config.json read before calling P90
- `ui/display_controller.py` or `ui/session_display.py` — add INCLUDED/OVERAGE row; modify threshold row to show calibration state
- New module candidate: `core/threshold_manager.py` — encapsulates config.json read, cold-start count, P90 call, and threshold state (calibrating / auto / manual)

</code_context>

<specifics>
## Specific Ideas

- Config file format (from user selection): `{ "overage_threshold_tokens": 88000 }`
- Threshold row format (from user selection):
  - Calibrating: `Token limit: Calibrating (3/10 sessions)`
  - Auto: `Token limit: 88,000 tokens (P90)`
  - Manual: `Token limit: 88,000 tokens (manual)`
- Overage status row (from user selection):
  - `Status: ✅ INCLUDED`  or  `Status: 🔴 OVERAGE`
  - Suppressed entirely while calibrating

</specifics>

<deferred>
## Deferred Ideas

- **Session reset model detection** — PROJECT.md Active requirements include "Detects whether the session reset model is rolling 5-hour windows or calendar-day." This is not mapped to Phase 2 requirements (THRS-01/02/03). Flag for Phase 3 consideration — it affects when the overage pool resets, which is directly relevant to Phase 3's billing-cycle calculation.
- **Configurable cold-start minimum** — User chose hardcoded 10. If a future admin wants to lower/raise this, expose it in config.json. Defer.
- **CLI `--custom-limit-tokens` as override path** — Existing flag stays for power users running one-off runs, but it is NOT the persistent override. No new wiring needed for Phase 2.

</deferred>

---

*Phase: 02-threshold-detection*
*Context gathered: 2026-05-08*
