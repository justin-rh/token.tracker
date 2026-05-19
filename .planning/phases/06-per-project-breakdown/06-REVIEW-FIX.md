---
phase: 06-per-project-breakdown
fixed_at: 2026-05-19T00:00:00Z
review_path: .planning/phases/06-per-project-breakdown/06-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-05-19
**Source review:** .planning/phases/06-per-project-breakdown/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: Test 4 billing-month filter has a fragile day-of-month assumption

**Files modified:** `tests/test_project_breakdown.py`
**Commit:** cfd5ab5
**Applied fix:** Imported `_derive_billing_cycle_start` into the test module. In
`test_billing_month_window_filtering`, replaced the `_days_ago_str(5)` anchor with a
timestamp derived directly from `billing_start`: call `_derive_billing_cycle_start(1,
today=today_utc)` (UTC date, matching the production logic), then build `in_billing_ts`
from `billing_start.year/month/day` at noon UTC. The test now passes on any day of the
month regardless of billing cycle position.

---

### WR-02: Display-name key collision silently merges unrelated projects

**Files modified:** `core/project_breakdown.py`
**Commit:** b1a0d18
**Applied fix:** Added a comment adjacent to the `display_name = slug.split("-")[-1]`
assignment documenting the known merge-on-collision limitation (D-01). Added a
`logger.debug` call immediately after the assignment that fires whenever `display_name`
is already present in `today_tokens` or `month_tokens`, logging the display name and
full slug so collisions are traceable at debug log level.

---

### WR-03: `_derive_billing_cycle_start` uses local date; `today_date` uses UTC

**Files modified:** `core/project_breakdown.py`
**Commit:** b1a0d18
**Applied fix:** Updated `_derive_billing_cycle_start` to accept an optional
`today: date | None = None` parameter (defaults to `date.today()` for backward
compatibility) with a docstring explaining callers should pass the UTC date. In
`compute_project_breakdown`, reordered the two lines so `today_date` (UTC) is derived
first, then passed as `today=today_date` to `_derive_billing_cycle_start`. Both
variables now use the same UTC reference date, eliminating the local/UTC cross-midnight
skew.

---

### WR-04: `format_active_session_screen` project rows use `{name:<22}` not `_col_pad`

**Files modified:** `ui/session_display.py`
**Commit:** 73d773b
**Applied fix:** Replaced `f"  [dim]{name:<22}[/] {_fmt_tokens(toks)}"` with
`f"  [dim]{_col_pad(name, 22)}[/] {_fmt_tokens(toks)}"` in both the `today` and
`billing_month` row loops (lines 333-335). `_col_pad` is applied to `name` before the
Rich markup tags are added, which is the correct order — the helper strips markup before
measuring, so applying it inside `[dim]...[/]` measures only the plain name string.

---

_Fixed: 2026-05-19_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
