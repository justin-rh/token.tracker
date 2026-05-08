# Phase 3: Overage Pool Dashboard - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Display whether current usage is on included tokens or burning the $500 overage pool — and how fast. Show est. dollars spent from the pool in the current billing period, pool % remaining as a progress bar, $/hr burn rate, and projected pool exhaustion time. Pool spend state must persist across terminal restarts. Pool size and billing cycle start are user-configurable in config.json. All cost figures carry an "est." prefix.

Phase 3 extends the INCLUDED/OVERAGE status row built in Phase 2 — it does not replace it.

</domain>

<decisions>
## Implementation Decisions

### Pool Spend Accounting
- **D-01:** Pool spend = sum of `cost.total_cost_usd` from `statusline.jsonl` for all sessions in the current billing period where `tokens_used > threshold_tokens` (OVERAGE sessions). Only OVERAGE-flagged sessions contribute — INCLUDED sessions are excluded.
- **D-02:** When a session crosses the threshold mid-run (started INCLUDED, ended OVERAGE), count the **full session cost**. Simpler to implement; overage sessions typically consume most of their cost in the overage portion anyway. Slight over-estimate is acceptable for a local approximation — all figures carry "est." prefix (DISP-02).
- **D-03:** Pool spend is recomputed from `statusline.jsonl` on each startup/refresh (not accumulated from a running counter). The persisted state file (`pool_spend.json`) serves as a startup cache and billing cycle anchor, not a source of truth that can drift.

### State Persistence (OVGE-05)
- **D-04:** Write `~/.claude-monitor/pool_spend.json` containing: `pool_spend_usd` (float), `billing_cycle_start` (ISO date string), `last_updated` (ISO timestamp). Same directory as `config.json` and `last_used.json`.
- **D-05:** Billing cycle start date is stored in **`config.json`** (not `pool_spend.json`). Key: `billing_cycle_start_day` (integer 1–28, default 1). User edits one config file for all overrides — consistent with Phase 2 pattern.
- **D-06:** On startup, if `pool_spend.json` exists, use its `billing_cycle_start` to filter `statusline.jsonl` entries. If the file doesn't exist, derive the billing period start from `config.json → billing_cycle_start_day` and today's date, then recompute from logs.

### Config File Additions (OVGE-06)
- **D-07:** Add two new keys to `~/.claude-monitor/config.json`:
  - `pool_size_usd` (float, default 500.0) — the total pool amount
  - `billing_cycle_start_day` (int 1–28, default 1) — day of month the billing period resets
- **D-08:** These keys are optional; defaults apply when absent. Same malformed-value pattern as Phase 2 (log warning + use default).

### Burn Rate and Projection (OVGE-04)
- **D-09:** `$/hr` burn rate is derived from the **current active session**: `session_cost_usd / elapsed_session_minutes × 60`. Uses the same cost and elapsed-time values already present in the monitoring data.
- **D-10:** "Pool exhausted in X hours" projection = `(pool_size_usd - pool_spend_usd) / burn_rate_per_hr`. Rendered as hours + minutes (e.g., "~4h 23m remaining").
- **D-11:** Burn rate row and pool exhaustion projection are shown **only while in OVERAGE state**. While INCLUDED, these rows are hidden — they'd be meaningless and add visual noise.

### Display Layout (OVGE-01, OVGE-02, OVGE-03, DISP-02)
- **D-12:** The Phase 2 INCLUDED/OVERAGE status row stays in place. Phase 3 adds a new section below it (new separator line) with pool dashboard rows — only visible when status is known (not calibrating).
- **D-13:** All cost figures must carry "est." prefix in the UI — e.g., "Pool spent: est. $12.34 / $500.00".
- **D-14:** Pool % remaining is displayed as a Rich progress bar (reuse existing `_render_wide_progress_bar` pattern). Color: green > 50%, yellow > 20%, red ≤ 20%.

### Claude's Discretion
- Exact Rich markup and emoji choices for pool dashboard rows — consistent with existing session_display.py style
- Whether `pool_spend.json` is written on every refresh cycle or only on startup/shutdown
- Error handling if `statusline.jsonl` is missing or empty (fall back to pool_spend_usd = 0.0, show "est. $0.00")
- Whether to add a new `PoolStateManager` class (parallel to `ThresholdManager`) or inline the logic

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 3 Requirements
- `.planning/REQUIREMENTS.md` — OVGE-01 through OVGE-06 and DISP-02 are the full scope. Read for exact acceptance criteria.

### Prior Phase Context
- `.planning/phases/02-threshold-detection/02-CONTEXT.md` — D-10: "This status row is the foundation Phase 3 builds on." D-03/D-04: config.json location and key naming pattern. Phase 3 extends the threshold section rendered in session_display.py:269-312.
- `.planning/phases/01-windows-foundation/01-CONTEXT.md` — D-06/D-07: statusline.jsonl as primary cost source.

### Source Files (Key Integration Points)
- `core/statusline_cost.py` — `read_statusline_costs()` returns `{session_key: cost_usd}`. Phase 3 reads this to sum OVERAGE session costs.
- `core/threshold_manager.py` — `ThresholdState` (status, threshold_tokens). Pool accounting needs this to classify each session as INCLUDED vs OVERAGE.
- `monitoring/orchestrator.py` — `_fetch_and_process_data()` is where pool state computation slots in alongside threshold state.
- `ui/session_display.py:269–312` — Phase 2 threshold rows. Phase 3 appends pool dashboard rows immediately below.
- `core/settings.py` — `LastUsedParams` pattern in `~/.claude-monitor/` — model for new config.json keys and pool_spend.json.

### Research Reference
- `.planning/research/ARCHITECTURE.md` — Component map. Phase 3 adds PoolStateManager analogous to ThresholdManager.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `statusline_cost.py:read_statusline_costs()` — Returns all session costs keyed by session_id/timestamp. Phase 3 filters this by billing period + OVERAGE status.
- `session_display.py:_render_wide_progress_bar(percentage)` — 50-char Rich bar with green/yellow/red color. Reuse directly for pool % remaining bar.
- `threshold_manager.py:ThresholdState` — Exposes `threshold_tokens` and `status`. Pool computation reads `threshold_tokens` to flag sessions.
- `settings.py:LastUsedParams` — Pattern for reading/writing JSON to `~/.claude-monitor/`. Pool state file follows same atomic write pattern (write to .tmp, rename).
- `core/plans.py:DEFAULT_TOKEN_LIMIT` — Used as fallback during calibration; pool accounting should also handle calibration state (no threshold = no OVERAGE classification = show $0.00).

### Established Patterns
- `config.json` in `~/.claude-monitor/` for persistent user configuration (Phase 2 D-03)
- `kwargs.get("threshold_state")` in `format_active_session_screen` — Phase 3 adds `kwargs.get("pool_state")` the same way
- All cost rows in session_display.py follow: `"💲 [value]Label:[/]   [markup]{value}[/]"` pattern
- Atomic file writes: write to `.tmp` then `temp_file.replace(final_path)` (see `LastUsedParams.save()`)

### Integration Points
- `monitoring/orchestrator.py:_fetch_and_process_data()` — Add pool state computation after threshold state (line ~177); include `pool_state` in the monitoring_data dict passed to callbacks.
- `ui/session_display.py:format_active_session_screen()` — Read `pool_state` from `kwargs`; append pool rows after the Phase 2 threshold section (line ~312).
- New module: `core/pool_state_manager.py` — Analogous to `threshold_manager.py`. Encapsulates: read config.json for pool settings, read statusline.jsonl, filter by billing period + OVERAGE, return PoolState dataclass.

</code_context>

<specifics>
## Specific Ideas

- Pool spend row format: `"🏦 [value]Pool spent:[/]   est. $12.34 / $500.00"`
- Pool progress bar: reuse `_render_wide_progress_bar` with pool_pct = (pool_spend / pool_size × 100)
- Burn rate row (OVERAGE only): `"🔥 [value]Pool burn:[/]    est. $2.40/hr — ~4h 23m remaining"`
- All cost values prefixed with "est." inline in the string, not as a separate label (DISP-02)

</specifics>

<deferred>
## Deferred Ideas

- **Session reset model detection** (from Phase 2 deferred) — Rolling 5-hour windows vs calendar-day. Not needed for Phase 3: pool tracking is per billing month (configurable start day), not per session window. This concern is about session token limits, not pool period. Can stay deferred.
- **Billing API integration** (v2 BILL-01) — Query Anthropic account API for authoritative pool spend. Out of scope for v1.
- **Alert on pool threshold** (v2 BILL-02) — Terminal bell + color change at user-configurable % exhausted. Out of scope for v1.
- **Historical pool spend chart** (v2 ANLX-01) — Out of scope for v1.

</deferred>

---

*Phase: 03-overage-pool-dashboard*
*Context gathered: 2026-05-08*
