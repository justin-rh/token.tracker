---
phase: 04-web-data-foundation
plan: "05"
subsystem: session-display
tags: [session-display, web-usage, d-17, d-18, d-19, utilization, phase-4]
dependency_graph:
  requires:
    - 04-01  # WebUsageData frozen dataclass in core/models.py
    - 04-04  # web_usage kwarg plumbing through display_controller -> session_display
  provides:
    - format_active_session_screen(web_usage=)  # D-17 Utilization+Resets rows when web data present
    - format_active_session_screen(last_web_sync=)  # D-19 Last web sync footer
    - D-18 fallback suffix on P90/manual token limit label
  affects:
    - cli/main.py  # 04-06 will pass last_web_sync kwarg once WebPoller wired
tech_stack:
  added: []
  patterns:
    - "dt_timezone alias for datetime.timezone to avoid shadowing by 'timezone: str' parameter"
    - "_show_threshold_rows guard: suppress entire threshold block when web_usage is not None (Pitfall 7)"
    - "max(0, ...) floor on countdown seconds prevents negative display"
key_files:
  created: []
  modified:
    - ui/session_display.py
decisions:
  - "Aliased datetime.timezone as dt_timezone to avoid name collision with the 'timezone: str' positional parameter of format_active_session_screen()"
  - "_show_threshold_rows bool guard suppresses entire Phase 2 threshold block (calibrating/auto/manual) when web_usage is present — prevents Pitfall 7 dual-display conflict"
  - "D-18 suffix '(est. — web unavailable)' computed inside _show_threshold_rows block; when web_usage is None the block runs so suffix condition is always '' (unreachable but harmless)"
  - "web_usage block placed after pool_state block so pool dashboard rows (Phase 3) are always independent of web data"
  - "last_web_sync kwarg checked with 'if last_sync:' to handle both None and absent kwarg uniformly"
metrics:
  duration: "298 seconds (~5 minutes)"
  completed: "2026-05-19"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
  files_created: 0
---

# Phase 4 Plan 5: session_display.py web usage display rows Summary

Utilization % with progress bar + reset countdown labeled "via claude.ai" (D-17), P90/manual fallback suffix "(est. — web unavailable)" (D-18), and "Last web sync: HH:MM:SS" footer (D-19) added to format_active_session_screen(); threshold rows suppressed when web data present.

## What Was Built

Three display branches added to `ui/session_display.py` `format_active_session_screen()`, covering all D-17/D-18/D-19 decisions from 04-CONTEXT.md:

**D-17 (web_usage present):**
- `_show_threshold_rows` guard: wraps entire Phase 2 threshold block with `threshold_state is not None and kwargs.get("web_usage") is None`. When web data is available, the calibrating/P90/manual rows are fully suppressed (Pitfall 7 prevention).
- Utilization row: `🌐 [value]Utilization:[/]   <bar> 64.3%  [dim]via claude.ai[/]` — reuses `_render_wide_progress_bar(web_usage.utilization_pct)`.
- Resets In row: `⏱  [value]Resets in:[/]     2h 0m` — countdown from `web_usage.reset_at - datetime.now(dt_timezone.utc)`, floored at 0 via `max(0, ...)`.

**D-18 (web_usage absent):**
- `(est. — web unavailable)` appended inside `[dim]` markup to both the P90 branch (`[dim](P90) (est. — web unavailable)[/]`) and the manual branch (`[dim](manual) (est. — web unavailable)[/]`).
- The suffix is only reachable when `_show_threshold_rows` is True (i.e., `web_usage is None`), so the `is not None` condition inside is always False there — the suffix always renders when the block runs.

**D-19 (last_web_sync kwarg):**
- `🔄 [dim]Last web sync: {last_sync.strftime('%H:%M:%S')}[/]` footer appended inside the web_usage block when `kwargs.get("last_web_sync")` is truthy.
- Absent when `last_web_sync` not yet passed (Plan 06 wires this through).

**Alias fix (deviation Rule 1):**
- `datetime.timezone` imported as `dt_timezone` to avoid shadowing by the `timezone: str` positional parameter of `format_active_session_screen()`. Using `timezone.utc` inside the function caused `AttributeError: 'str' object has no attribute 'utc'`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add web_usage display rows to format_active_session_screen() | cd2584a | ui/session_display.py |

## Decisions Made

- `dt_timezone` alias for `datetime.timezone` prevents parameter name collision with `timezone: str` in the function signature.
- `_show_threshold_rows = threshold_state is not None and kwargs.get("web_usage") is None` provides a single clear suppression gate for the entire Phase 2 block.
- Pool state block guard (`pool_state is not None and threshold_state is not None and threshold_state.status != "calibrating"`) left unchanged — pool dashboard rows are independent of web data presence.
- `last_web_sync` rendered with `strftime('%H:%M:%S')` matching the D-19 spec format exactly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] dt_timezone alias to avoid parameter name shadowing**
- **Found during:** Task 1 smoke test — `AttributeError: 'str' object has no attribute 'utc'`
- **Issue:** `format_active_session_screen()` has a `timezone: str` positional parameter that shadows the `datetime.timezone` module-level import inside the function body.
- **Fix:** Changed import from `from datetime import datetime, timezone` to two lines: `from datetime import datetime` and `from datetime import timezone as dt_timezone`. Updated `datetime.now(timezone.utc)` to `datetime.now(dt_timezone.utc)`.
- **Files modified:** ui/session_display.py (import block + one usage site)
- **Commit:** cd2584a (included in same task commit)

## Threat Mitigation Verification

- T-04-05-01 (Tampering — utilization_pct): Rendered as `{:.1f}%` — no raw string interpolation of API response.
- T-04-05-02 (DoS — negative countdown): `total_secs = max(0, int(delta.total_seconds()))` — floor at 0 implemented.
- T-04-05-04 (DoS — Calibrating + web_usage conflict): `_show_threshold_rows` guard suppresses entire threshold block when web_usage is not None — verified in smoke test (Test 4).

## Known Stubs

None — all three display branches are fully wired. The `last_web_sync` kwarg renders when present and is silently skipped when absent; Plan 06 will wire the actual datetime value through from the WebPoller.

## Self-Check: PASSED

Files modified exist:
- ui/session_display.py — FOUND

Commits exist:
- cd2584a — feat(04-05): add web usage display rows to session_display.py — FOUND
