---
phase: 06-per-project-breakdown
plan: "04"
subsystem: ui
tags: [session-display, layout, per-project, d07-removal, d08-relocate, d09-layout]

dependency_graph:
  requires:
    - phase: 06-01 (ProjectBreakdown dataclass in core/models.py)
    - phase: 06-03 (monitoring_data["project_breakdown"] populated by orchestrator)
  provides:
    - D-09 layout order in format_active_session_screen custom/pro/max5/max20 branch
    - Per-project side-by-side columns (Today est. / This month est.) in terminal dashboard
    - D-07 rows removed (Cost Usage, Token Usage, Messages Usage, Time to Reset progress bars)
    - D-08 rows (Model Distribution, Burn Rate, Cost Rate) relocated after Last web sync
  affects: []

tech_stack:
  added: []
  patterns:
    - "_col_pad() helper for terminal-visible width padding — handles Rich markup tags and wide emoji correctly"
    - "Side-by-side column rendering via zip(left_lines, right_lines) with blank-padding to equalize lengths"
    - "_fmt_tokens() with M/k/plain tiers for readable token counts at any scale"

key_files:
  created: []
  modified:
    - ui/session_display.py

key_decisions:
  - "_col_pad() added because f-string :<N counts Python string length, not terminal columns — Rich markup tags and 📂 emoji overhead break naive padding"
  - "col_width=36 (widened from plan's 34) to fit 'M tok' suffix and emoji overhead in left column"
  - "D-08 rows placed INSIDE if web_usage is not None block — they only render when web data is active"
  - "Threshold/INCLUDED/OVERAGE rows absent when web_usage is present — intentional per Pitfall 7 (Phase 4 design); web Utilization row is the authoritative replacement"
  - "_fmt_tokens uses M suffix for >= 1_000_000 to handle million-scale token counts without truncation"

requirements-completed:
  - PROJ-01
  - PROJ-02
  - PROJ-03

metrics:
  duration: "multi-session (across 2026-05-19 context windows)"
  completed: "2026-05-19"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 6 Plan 04: Restructure session_display — D-07/D-08/D-09/D-14 Layout Summary

**Per-project side-by-side token columns (Today est. / This month est.) added to terminal dashboard; four D-07 progress bars removed from custom/pro branch; Model Distribution, Burn Rate, Cost Rate relocated after Last web sync.**

## What Was Built

`ui/session_display.py` restructured to implement the D-09 layout order in the `custom/pro/max5/max20` branch of `format_active_session_screen`:

- **D-07 removal:** `💰 Cost Usage`, `📊 Token Usage`, `📨 Messages Usage`, `⏱️ Time to Reset` progress bars deleted from the custom branch (they duplicated web data; kept in the `else` branch unchanged per D-10)
- **D-08 relocation:** `🤖 Model Distribution`, `🔥 Burn Rate`, `💲 Cost Rate` rows moved inside `if web_usage is not None:` block — now appear after the Last web sync row
- **D-09 per-project section:** New side-by-side columns inserted between the Phase 3 pool section and the Phase 4 web section; guarded by `project_breakdown is not None and (project_breakdown.today or project_breakdown.billing_month)`
- **`_fmt_tokens()` helper:** Module-level function with M/k/plain tiers added for readable token formatting at any scale
- **`_col_pad()` helper:** Terminal-visible width padding that strips Rich markup tags and accounts for wide emoji (📂 = 2 columns) before computing padding — fixes alignment issues that naive f-string `:<N` cannot handle

Human smoke-test approved: layout renders correctly with per-project columns visible, D-07 rows absent, D-08 rows after Last web sync, and Pitfall 7 threshold suppression confirmed intentional.

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Restructure custom branch — remove D-07, relocate D-08, insert D-09 | 7047e93 | ui/session_display.py |
| 1a | Wire project_breakdown through display_controller and cli/main.py | 2003d54 | ui/display_controller.py, cli/main.py |
| 1b | Fix column alignment — _col_pad() for terminal-visible width | d9ceb20 | ui/session_display.py |
| 1c | M suffix for million-scale tokens; col_width=36 | 7631770 | ui/session_display.py |
| 2 | Human smoke-test | (checkpoint approval) | — |

## Verification Results

- Import check: `python -c "from claude_monitor.ui.session_display import SessionDisplayComponent; print('OK')"` → `OK`
- "Cost Usage" absent from custom branch: confirmed
- "Token Usage" absent from custom branch: confirmed (present only in else branch)
- "Messages Usage" absent from custom branch: confirmed (else branch uses "Sent Messages" — plan criterion was stale on label)
- "Time to Reset" absent from custom branch: confirmed (present only in else branch)
- `project_breakdown = kwargs.get` present: 1 match (line 327)
- `_fmt_tokens` occurrences: 3 (definition + 2 call sites)
- "Today (est.)" header: 1 match
- "This month (est.)" header: 1 match
- Model Distribution / Burn Rate / Cost Rate: inside web_usage block only
- Session Cost in else branch: confirmed present (D-10 — else branch unchanged)
- Human smoke-test: approved (Pitfall 7 threshold suppression confirmed intentional when web data active)

## Deviations from Plan

### Auto-fixed Issues

**1. project_breakdown not passed to session_display**
- **Found during:** Initial smoke-test cycle
- **Issue:** `display_controller.py` and `cli/main.py` were not passing `project_breakdown` from `monitoring_data` to `format_active_session_screen` via kwargs — the kwarg was consumed but never populated at call sites
- **Fix:** Added `project_breakdown=monitoring_data.get("project_breakdown")` to both call sites
- **Files modified:** ui/display_controller.py, cli/main.py
- **Committed in:** 2003d54

**2. Column alignment broken by Rich markup + emoji overhead**
- **Found during:** Visual smoke-test (left column misaligned)
- **Issue:** f-string `:<34` pads by Python string length, not terminal-visible width; Rich markup tags `[value]`, `[dim]`, `[/]` add string chars without terminal columns; 📂 emoji takes 2 columns but 1 Python char
- **Fix:** Added `_col_pad(s, width)` helper that strips markup via regex then computes east-asian-width-aware column count before padding; widened col_width to 36
- **Files modified:** ui/session_display.py
- **Committed in:** d9ceb20, 7631770

---

**Total deviations:** 2 auto-fixed (1 missing wire-up, 1 display alignment)
**Impact on plan:** Both fixes required for correctness. No scope creep.

## Self-Check: PASSED

- `ui/session_display.py` restructured and committed across 7047e93, d9ceb20, 7631770
- D-07 rows absent from custom branch — import check passes, grep confirms
- D-09 per-project section present at line 326 with correct guard
- D-08 rows inside web_usage block at lines 372-394
- Human smoke-test approved 2026-05-19
