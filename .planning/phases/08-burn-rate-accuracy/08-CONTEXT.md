# Phase 8: Burn Rate Accuracy — Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the broken pool burn rate formula (`session_cost / elapsed_session_minutes`) in `ui/session_display.py` with a rolling delta calculation driven by a `collections.deque` ring buffer of `(timestamp, pool_spend_usd)` tuples maintained in the monitoring orchestrator.

The burn rate row in the dashboard (🔥 Pool burn: est. $/hr) changes only when `pool_spend_usd` actually increases — not when session cost or uptime changes. The row is hidden until at least two spend-change samples accumulate.

Out of scope: token burn rate (tokens/min), any change to the threshold/P90 pipeline, new config keys.

</domain>

<decisions>
## Implementation Decisions

### Ring Buffer Architecture
- **D-01:** Ring buffer lives in `monitoring/orchestrator.py` as an instance attribute (`self._burn_rate_buffer: collections.deque`). Pre-decided in STATE.md; consistent with Phase 4/5 pattern of extending the orchestrator for new monitoring state.
- **D-02:** Buffer stores `(timestamp: float, pool_spend_usd: float)` tuples — `time.time()` for the timestamp, `pool_state.pool_spend_usd` for the spend value.
- **D-03:** Buffer is **in-memory only** — starts empty on each process restart. The burn rate row stays hidden (per BURN-02) until 2+ spend samples accumulate. No new disk state to manage.

### Rolling Window
- **D-04:** Window = **30 minutes** (1800 seconds). The deque is created with `maxlen` set to cap sample count. Since samples are inserted only on spend change (not every 10s cycle), `maxlen` is a time-based cutoff enforced at read time: discard samples older than `now - 1800s` before computing the delta. No `maxlen` on the deque itself — use a soft time window filter.

### Sample Insertion Policy
- **D-05:** A new sample is appended to the ring buffer **only when `pool_spend_usd` increases from the last buffered value**. The orchestrator tracks `self._last_burn_sample_spend: float = 0.0` and compares after each `compute_pool_state()` call. If `pool_state.pool_spend_usd > self._last_burn_sample_spend`, append `(time.time(), pool_state.pool_spend_usd)` and update `_last_burn_sample_spend`. This keeps the buffer sparse but every entry meaningful.

### Billing Cycle Reset Handling
- **D-06:** When the orchestrator detects a billing cycle reset (new `pool_state.billing_cycle_start` differs from the previous cycle's value), **clear the ring buffer** (`self._burn_rate_buffer.clear()`) and reset `self._last_burn_sample_spend = 0.0`. The orchestrator already has access to `pool_state.billing_cycle_start` on every cycle — compare to a stored `self._last_billing_cycle_start` attribute. On first cycle, just store the value.

### Burn Rate Computation
- **D-07:** Burn rate is computed in the orchestrator at the end of `_fetch_and_process_data()`, after the ring buffer is updated. Filter buffer to samples within the 30-min window, then: `delta_spend / delta_time_hours` using the oldest and newest filtered samples.
- **D-08:** When `len(filtered_samples) < 2`, set `burn_rate_usd_per_hr = None`. When `None`, the orchestrator passes `None` in `monitoring_data` and `session_display.py` omits the burn row entirely (satisfies BURN-02).

### Data Flow
- **D-09:** Add `"pool_burn_rate_usd_per_hr": float | None` to the `monitoring_data` dict in `_fetch_and_process_data()`. `session_display.py` reads this key from `kwargs` — same pattern as `web_usage`, `pool_state`, `project_breakdown`. Remove the inline burn rate calculation from `session_display.py` (lines 302–306).

### Claude's Discretion
- Exact attribute names for orchestrator state (`_burn_rate_buffer`, `_last_burn_sample_spend`, `_last_billing_cycle_start`) — planner chooses consistent naming.
- Whether to extract the burn rate computation into a private `_compute_burn_rate()` helper or keep it inline — planner's call based on complexity.
- How to handle a hypothetical decrease in pool_spend_usd mid-cycle (e.g., manual seed adjustment) — ignore (don't insert a sample when spend decreases) is the natural outcome of the `> last_sample` policy (D-05).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — BURN-01, BURN-02 acceptance criteria
- `.planning/ROADMAP.md` §Phase 8 — success criteria and phase goal

### Implementation Files (read before editing)
- `monitoring/orchestrator.py` — ring buffer and burn rate computation go here; `_fetch_and_process_data()` is the integration point
- `ui/session_display.py` lines 299–316 — current broken burn rate formula to replace; reads from `kwargs`
- `core/pool_state_manager.py` — `PoolState.pool_spend_usd` and `PoolState.billing_cycle_start` are the source values

### Established Patterns
- `monitoring/orchestrator.py` `_web_poller` attribute pattern (Phase 4) — follow same `Optional[Any]` / instance-attr pattern for new buffer state
- `monitoring_data` dict construction in `_fetch_and_process_data()` — new `pool_burn_rate_usd_per_hr` key follows same pattern as `web_usage`, `pool_state`

</canonical_refs>

<code_context>
## Existing Code Insights

### Current Broken Formula (to replace)
- `ui/session_display.py:302–306` — `burn_rate_per_hr = (session_cost / max(1, elapsed_session_minutes)) * 60` — depends on session cost and uptime, changes constantly regardless of pool spend. Remove entirely.

### Reusable Assets
- `monitoring_data` dict in `orchestrator.py:210–221` — add one key; no structural change needed
- `pool_state.pool_spend_usd` and `pool_state.billing_cycle_start` already computed and available in `_fetch_and_process_data()` before the monitoring_data dict is assembled
- `pool_state.is_overage` already gates the burn rate block in `session_display.py:300` — keep this gate; only show burn rate when is_overage AND burn_rate is not None

### Integration Points
- `monitoring/orchestrator.py __init__()` — add `self._burn_rate_buffer`, `self._last_burn_sample_spend`, `self._last_billing_cycle_start` attributes
- `monitoring/orchestrator.py _fetch_and_process_data()` — update ring buffer after `pool_state` is computed; compute burn rate; add to `monitoring_data`
- `ui/session_display.py` burn rate block — replace inline formula with `kwargs.get("pool_burn_rate_usd_per_hr")` read; None → omit line

</code_context>

<specifics>
## Specific Ideas

- The 30-minute window is enforced at read time (filter buffer to `now - 1800s`), not via `deque(maxlen=N)`. This avoids calculating a fixed maxlen from the variable sampling rate (samples only on change, not every 10s).
- Reset detection compares `pool_state.billing_cycle_start` (str) to a stored previous value — simple string equality, no datetime parsing needed at the orchestrator level.
- "est." prefix is already in the display string template; no change needed to that label.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-burn-rate-accuracy*
*Context gathered: 2026-05-20*
