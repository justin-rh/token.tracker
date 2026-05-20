# Phase 7: Code Quality — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 07-code-quality
**Areas discussed:** WR-01 (date-skew fix approach), WR-02 (collision warning detail), WR-04 (_col_pad coverage), WR-03 (UTC normalization scope)

---

## WR-01: Date-skew Fix Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Parameter injection | Add `today: date \| None = None` to `_derive_billing_cycle_start()` and thread through `compute_pool_state()`. Matches project_breakdown.py pattern. No new deps. | ✓ |
| freezegun / time-machine | Keep production code unchanged; freeze time in tests using a library. Simpler test changes but adds a test dep and doesn't fix UTC vs. local inconsistency in production. | |
| Relative fixture dates | Replace hardcoded `'2026-05-08'` with `date.today() - timedelta(days=N)` in fixtures. No prod code change but still uses local time — fragile. | |

**User's choice:** Parameter injection
**Notes:** Consistent with project_breakdown.py existing pattern. WR-01 and WR-03 unified into one change.

---

## WR-02: Collision Warning Detail

| Option | Description | Selected |
|--------|-------------|----------|
| Both slugs | Track `slug_map: dict[str, str]` alongside token dicts; WARNING includes both colliding slugs | ✓ |
| Just the incoming slug | Change `debug → warning`, keep current message (incoming slug only). Simpler but doesn't fully meet QUAL-02. | |

**User's choice:** Both slugs
**Notes:** Adds `slug_map` local var to `compute_project_breakdown()`; no module-level state.

---

## WR-04: _col_pad Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Test + visual spot-check | Add unit test with markup-containing project name + manual emoji spot-check | ✓ |
| Tests only | Existing test suite passing is sufficient | |
| Visual inspection only | Run tracker with markup project name, no automated test | |

**User's choice:** Test + visual spot-check
**Notes:** Staged changes to session_display.py pre-exist — verify with `git diff --staged` before planning.

---

## WR-03: UTC Normalization Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Unified with WR-01 | Same `today: date \| None = None` param; default uses UTC. One cohesive change. | ✓ |
| Separate internal swap | Standalone `date.today()` → `datetime.now(UTC).date()` swap, no parameter added. | |

**User's choice:** Unified with WR-01
**Notes:** WR-01 and WR-03 are one change to `_derive_billing_cycle_start()`.

---

## Claude's Discretion

- Commit strategy (atomic per-fix vs. combined)
- Specific `today` date values to inject in test fixtures

## Deferred Ideas

None.
