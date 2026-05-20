---
plan: 08-02
phase: 08-burn-rate-accuracy
status: complete
completed: 2026-05-20
commit: e5fa895
---

# Plan 08-02 Summary: Display Update + Burn Rate Tests

## What Was Built

Replaced the broken inline burn rate formula in `session_display.py` with a thin kwargs read from `pool_burn_rate_usd_per_hr` (produced by Plan 08-01). Added `tests/test_burn_rate.py` with 4 unit tests covering ring buffer logic.

## Key Changes

**`ui/session_display.py`** (lines 299-316 replaced)
- Old: computed `burn_rate_per_hr = (session_cost / max(1, elapsed_session_minutes)) * 60`
- New: reads `burn_rate_usd_per_hr = kwargs.get("pool_burn_rate_usd_per_hr")`
- When `None`: row omitted entirely (BURN-02 — insufficient buffer history)
- When non-None: formats `est. $/hr` and pool exhaustion estimate as before
- `est.` prefix preserved; outer `if pool_state.is_overage:` gate unchanged

**`tests/test_burn_rate.py`** (new file, 4 tests)
- `test_burn_rate_none_when_empty` — empty buffer → len(filtered) < 2
- `test_burn_rate_none_with_one_sample` — single sample → still insufficient
- `test_burn_rate_computed_from_two_samples` — $0.50 → $1.50 over 1hr = $1.00/hr
- `test_billing_cycle_reset_clears_buffer` — reset condition clears buffer and sentinel

## Verification

- `python -m pytest tests/test_burn_rate.py -v` → 4 passed
- `python -m pytest tests/ -x -q` → 83 passed (no regressions)
- `grep "pool_burn_rate_usd_per_hr" ui/session_display.py` → kwargs.get line present
- Old formula `session_cost / max(1, elapsed_session_minutes)` removed from burn rate block

## Self-Check: PASSED

All must_haves satisfied:
- Burn rate row reads `pool_burn_rate_usd_per_hr` from kwargs — no inline formula
- Row absent from display when `pool_burn_rate_usd_per_hr` is None (BURN-02)
- Row shows `est. $/hr` and pool exhaustion when value is a positive float (BURN-01)
- 4 unit tests confirm None for <2 samples, credible rate after multiple samples, reset clears buffer
