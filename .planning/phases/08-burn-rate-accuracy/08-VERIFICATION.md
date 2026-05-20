---
phase: 08-burn-rate-accuracy
verified: 2026-05-20T00:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Phase 8: Burn Rate Accuracy Verification Report

**Phase Goal:** Pool burn rate shown in the dashboard reflects actual pool_spend_usd velocity over a rolling window rather than current-session cost divided by elapsed time
**Verified:** 2026-05-20
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1   | The $/hr figure in the dashboard changes only when pool_spend_usd changes, not when session cost or uptime changes | VERIFIED | Orchestrator only appends to buffer on strict `pool_spend_usd > _last_burn_sample_spend` increase (orchestrator.py:232-234). Display reads `kwargs.get("pool_burn_rate_usd_per_hr")` (session_display.py:303) — no session_cost or elapsed_time in the burn rate row. Old formula at lines 379/390 belongs to the separate Cost Rate $/min row, not pool burn rate. |
| 2   | The burn rate row is absent from the display when fewer than two pool_spend_usd samples exist in the rolling window | VERIFIED | Orchestrator sets `burn_rate_usd_per_hr = None` when `len(_filtered) < 2` (orchestrator.py:248). Display gates `if burn_rate_usd_per_hr is not None:` before appending to screen_buffer (session_display.py:304). `screen_buffer.append(...)` is inside that guard — no row written when None. |
| 3   | After pool spend accumulates across multiple monitoring cycles the burn rate stabilizes to a credible $/hr figure | VERIFIED | `test_burn_rate_computed_from_two_samples` confirms: $0.50 → $1.50 over 3600s → 1.0 $/hr (asserted `abs(rate - 1.0) < 0.01`). Full pipeline wired: orchestrator → monitoring_data → cli.on_data_update → display_controller.create_data_display → session_display kwargs. |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `monitoring/orchestrator.py` | Ring buffer state attributes and burn rate computation in `_fetch_and_process_data()` | VERIFIED | Contains `_burn_rate_buffer`, `_last_burn_sample_spend`, `_last_billing_cycle_start` in `__init__`; ring buffer update + computation block at lines 215-248; `pool_burn_rate_usd_per_hr` key in monitoring_data at line 256 |
| `ui/session_display.py` | Burn rate row reads from kwargs not inline formula | VERIFIED | Line 303: `burn_rate_usd_per_hr = kwargs.get("pool_burn_rate_usd_per_hr")`. Old `(session_cost / max(1, elapsed_session_minutes)) * 60` formula entirely absent from the pool burn rate block. |
| `tests/test_burn_rate.py` | Unit tests for ring buffer logic | VERIFIED | 4 tests present and passing: `test_burn_rate_none_when_empty`, `test_burn_rate_none_with_one_sample`, `test_burn_rate_computed_from_two_samples`, `test_billing_cycle_reset_clears_buffer` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `monitoring/orchestrator.py _fetch_and_process_data()` | `monitoring_data['pool_burn_rate_usd_per_hr']` | ring buffer filter + delta computation | WIRED | Line 248: `burn_rate_usd_per_hr = None` (fallback); line 256: key assigned in dict |
| `pool_state.pool_spend_usd` | `_burn_rate_buffer` | `_last_burn_sample_spend` comparison | WIRED | Line 232: `if pool_state.pool_spend_usd > self._last_burn_sample_spend:` gates append |
| `monitoring_data['pool_burn_rate_usd_per_hr']` | `ui/session_display.py` burn rate block | `kwargs.get('pool_burn_rate_usd_per_hr')` | WIRED | cli/main.py:235 passes to `display_controller.create_data_display()`; display_controller.py:293 assigns to `processed_data`; passed as `**processed_data` to `format_active_session_screen`; read at session_display.py:303 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `ui/session_display.py` burn rate row | `burn_rate_usd_per_hr` | `kwargs.get("pool_burn_rate_usd_per_hr")` from orchestrator ring buffer | Yes — computed from `pool_state.pool_spend_usd` which is derived from JSONL blocks | FLOWING |
| `monitoring/orchestrator.py` | `burn_rate_usd_per_hr` local variable | `_burn_rate_buffer` filtered to 30-min window; delta of real `pool_spend_usd` values | Yes — JSONL-sourced `pool_spend_usd` fed through `compute_pool_state(blocks, threshold_state)` | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| 4 burn rate unit tests pass | `python -m pytest tests/test_burn_rate.py -v` | 4 passed in 0.06s | PASS |
| Full test suite — no regressions | `python -m pytest tests/ -x -q` | 83 passed in 0.66s | PASS |
| Orchestrator instantiates with ring buffer attributes | `python -c "from monitoring.orchestrator import MonitoringOrchestrator; import collections; o = MonitoringOrchestrator(); assert isinstance(o._burn_rate_buffer, collections.deque)"` | 0 exit, no assertion error | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| BURN-01 | 08-01, 08-02 | Pool burn rate ($/hr) derived from rate of change of pool_spend_usd over a rolling time window rather than current-session cost/elapsed-time | SATISFIED | Ring buffer in orchestrator computes delta_spend/delta_time from pool_spend_usd samples. Display reads pre-computed value from kwargs — no inline formula. |
| BURN-02 | 08-01, 08-02 | Burn rate row is hidden (not shown as $0.00) when insufficient history exists to compute a meaningful rate | SATISFIED | `burn_rate_usd_per_hr = None` when `len(_filtered) < 2`. Display gate `if burn_rate_usd_per_hr is not None:` omits row entirely. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `ui/session_display.py` | 379, 390 | `session_cost / max(1, elapsed_session_minutes)` | Info | These instances compute `cost_per_min` for the **Cost Rate $/min** row (web_usage section and non-custom-plan branch), not the pool burn rate row. Both are legitimate and unrelated to BURN-01/BURN-02. No action required. |

### Human Verification Required

None. All three success criteria are mechanically verifiable:

1. The $/hr value is computed exclusively from `pool_spend_usd` deltas (code-confirmed).
2. The row omission when `None` is code-confirmed with no rendering path that bypasses it.
3. The computation formula is unit-tested with exact arithmetic assertions.

### Gaps Summary

No gaps. All three roadmap success criteria are satisfied, both requirement IDs are covered, all artifacts exist and are substantive, all key links are wired end-to-end, and the test suite passes with 83/83 tests.

---

_Verified: 2026-05-20T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
