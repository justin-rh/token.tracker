# Phase 7: Code Quality — Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Four isolated correctness fixes carried forward from v2.0 code review. All are single-file edits with no cross-module dependencies. Each fix targets a specific well-scoped issue; no new capabilities are introduced.

Fixes in scope:
- **WR-01**: Test date-skew in `test_pool_state_manager.py` (and the `pool_state_manager.py` root cause)
- **WR-02**: Display-name collision detection bumped from DEBUG to WARNING with both colliding slugs identified
- **WR-03**: Billing cycle start comparisons use UTC-normalized datetimes throughout `pool_state_manager.py`
- **WR-04**: All per-project f-string segments containing Rich markup use `_col_pad()` in `session_display.py`

</domain>

<decisions>
## Implementation Decisions

### WR-01: Date-skew Fix Approach
- **D-01:** Use **parameter injection** — add `today: date | None = None` to `_derive_billing_cycle_start()` in `pool_state_manager.py` and thread it through `compute_pool_state()`. When `today is None`, default to `datetime.now(timezone.utc).date()` (see WR-03, D-04). Tests pass a fixed `date` to make them deterministic and timezone-independent.
- Matches the existing pattern in `project_breakdown._derive_billing_cycle_start()` exactly — no new dependencies, no freezegun library.

### WR-02: Collision Warning Detail
- **D-02:** Track a `slug_map: dict[str, str]` alongside `today_tokens` and `month_tokens` in `project_breakdown.compute_project_breakdown()`. When a `display_name` collision is detected, include **both** colliding slugs in the WARNING message.
- Example log format: `"project_breakdown: display_name collision — 'tracker' claimed by both '%s' and '%s' — tokens merged"` with both slugs interpolated.
- Change `logger.debug` → `logger.warning` at the collision detection site.

### WR-03: UTC Normalization Scope
- **D-03:** WR-03 is unified with WR-01 (D-01) — they are one cohesive change to `_derive_billing_cycle_start()`.
- When `today is None`, the default uses `datetime.now(timezone.utc).date()` (UTC), not `date.today()` (local). No separate internal swap needed.
- `_in_billing_period()` already handles timezone-aware comparisons correctly — no changes needed there.

### WR-04: _col_pad Coverage
- **D-04:** Acceptance bar is **test + visual spot-check**:
  1. Add or update a unit test that passes a project name containing Rich markup characters (e.g., `[bold]foo[/]`) through the per-project display row and asserts that column alignment is correct.
  2. Spot-check manually with an emoji-containing project name to verify columns align visually in the terminal.
- The staged changes to `session_display.py` may already apply the fix — verify and confirm before counting as done.

### Claude's Discretion
- Commit strategy: one commit per fix (atomic, traceable) vs. one combined commit — planner's choice based on implementation complexity.
- Test fixture structure for WR-01: specific `today` date values to inject are at planner/executor discretion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — QUAL-01, QUAL-02, QUAL-03, QUAL-04 acceptance criteria
- `.planning/ROADMAP.md` §Phase 7 — success criteria and phase goals

### Implementation Patterns (read before touching these files)
- `core/project_breakdown.py` — reference implementation of `_derive_billing_cycle_start(cycle_day, today=None)` pattern (WR-01/WR-03 target pattern)
- `core/pool_state_manager.py` — file requiring WR-01/WR-03 fixes
- `ui/session_display.py` — file requiring WR-04 fix (has staged changes — check git diff HEAD before editing)
- `tests/test_pool_state_manager.py` — test suite requiring WR-01 date-injection updates

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_col_pad(s, width)` in `ui/session_display.py:40` — markup-aware padding, already in place; WR-04 verifies all call sites use it
- `_derive_billing_cycle_start(cycle_day, today=None)` in `core/project_breakdown.py:67` — exact pattern to replicate in `pool_state_manager.py`
- `_deduplicate_entries` from `data/reader.py` — already imported in project_breakdown; not touched by Phase 7

### Established Patterns
- Frozen dataclass + factory function (`ThresholdState`/`get_threshold`, `PoolState`/`compute_pool_state`) — don't break this pattern
- `tmp_path` pytest fixture used everywhere in tests — inject `today` as a new parameter to `compute_pool_state()` following the same `config_dir=tmp_path` injection pattern
- All datetime arithmetic uses `datetime.now(timezone.utc)` — `date.today()` is the anomaly being fixed

### Integration Points
- `compute_pool_state(blocks, threshold_state, config_dir)` — signature gets a new optional `today: date | None = None` param; all callers currently pass no `today` and will default to UTC behavior unchanged
- `monitoring/orchestrator.py` calls `compute_pool_state()` — verify the call site still works after signature change (no-op since param is optional)
- `tests/test_pool_state_manager.py` — all `make_block()` fixture `start_time` values must be consistent with the injected `today` date

</code_context>

<specifics>
## Specific Ideas

- WR-01 and WR-03 are one unified change: `_derive_billing_cycle_start(cycle_day, today: date | None = None)` where `today` defaults to `datetime.now(timezone.utc).date()`. Do NOT implement them as two separate changes that could conflict.
- WR-02 requires a `slug_map: dict[str, str]` — this is a local variable inside `compute_project_breakdown()`, not a module-level or class-level cache.
- Staged changes to `session_display.py` and working-tree changes to `tray_manager.py` are pre-existing uncommitted work — check `git diff` and `git diff --staged` before planning WR-04 to avoid re-doing or conflicting with already-applied fixes.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-code-quality*
*Context gathered: 2026-05-20*
