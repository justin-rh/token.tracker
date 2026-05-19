---
phase: 06-per-project-breakdown
plan: "02"
subsystem: core/project_breakdown
tags: [compute, project-breakdown, tdd, jsonl, deduplication, wave-2]
dependency_graph:
  requires: [ProjectBreakdown dataclass in core/models.py (Plan 06-01)]
  provides: [compute_project_breakdown() in core/project_breakdown.py]
  affects: [monitoring/orchestrator.py (Plan 06-03), ui/session_display.py (Plan 06-04)]
tech_stack:
  added: []
  patterns: [TDD red-green, defaultdict accumulation, frozen dataclass factory, imported deduplication]
key_files:
  created:
    - core/project_breakdown.py
    - tests/test_project_breakdown.py
  modified: []
key_decisions:
  - "_deduplicate_entries imported from data/reader.py — zero duplication of deduplication logic"
  - "display_name = slug.split('-')[-1] (D-01) — last hyphen segment of Windows project slug"
  - "encoding='utf-8-sig' for all JSONL opens — strips Windows BOM transparently"
  - "PermissionError caught per-file with logger.warning + continue — locked session files do not halt scan"
  - "defaultdict(int) accumulates today_tokens and month_tokens keyed by display_name"
  - "Zero-token entries excluded before accumulation — no dead projects pollute the ranked lists"
metrics:
  duration: "~2 minutes"
  completed: "2026-05-19T20:09:05Z"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 6 Plan 02: compute_project_breakdown() Summary

**One-liner:** `core/project_breakdown.py` with `compute_project_breakdown()` factory: scans JSONL by project dir, deduplicates via imported helper, ranks top-5 by tokens for today (UTC) and billing month.

## What Was Built

New module `core/project_breakdown.py` implementing `compute_project_breakdown(data_path, config_dir) -> ProjectBreakdown`. Scans all JSONL files under `data_path` using `_find_jsonl_files`, deduplicates streaming entries via imported `_deduplicate_entries`, and aggregates token totals per project display name. Returns a frozen `ProjectBreakdown` with `today` and `billing_month` as top-5 ranked `(display_name, total_tokens)` tuples.

New test file `tests/test_project_breakdown.py` with 7 unit tests covering all specified behaviors.

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Create core/project_breakdown.py (TDD RED then GREEN) | 2602b28 | core/project_breakdown.py, tests/test_project_breakdown.py |

## Verification Results

- All 7 tests pass: `python -m pytest tests/test_project_breakdown.py -v` exits 0
- Import check: `python -c "from claude_monitor.core.project_breakdown import compute_project_breakdown; print('OK')"` → `OK`
- `grep -c "def _deduplicate_entries" core/project_breakdown.py` → `0` (not duplicated)
- `grep -c "_deduplicate_entries" core/project_breakdown.py` → `4` (import + call site + docstring mentions)
- `encoding="utf-8-sig"` present at line 147
- `PermissionError` caught at line 157
- `slug.split("-")[-1]` display name extraction at line 143

## TDD Gate Compliance

- RED gate: `ModuleNotFoundError: No module named 'core.project_breakdown'` confirmed before implementation
- GREEN gate: All 7 tests passed after implementation
- REFACTOR gate: No refactor needed — implementation was clean on first pass

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — all STRIDE mitigations from threat register applied:
- T-06-02-03: `json.JSONDecodeError` caught per-line; malformed lines skipped
- T-06-02-04: `PermissionError` caught per-file with `logger.warning + continue`
- T-06-02-05: `billing_cycle_start_day` validated as `int 1-28`; invalid values fall back to 1

## Self-Check: PASSED

- `core/project_breakdown.py` created and committed at 2602b28
- `tests/test_project_breakdown.py` created and committed at 2602b28
- `compute_project_breakdown` importable from `claude_monitor.core.project_breakdown`
- `def compute_project_breakdown` present in implementation
- No file deletions in commit
