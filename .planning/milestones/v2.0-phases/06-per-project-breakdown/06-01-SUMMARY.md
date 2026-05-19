---
phase: 06-per-project-breakdown
plan: "01"
subsystem: core/models
tags: [dataclass, models, per-project, wave-1]
dependency_graph:
  requires: []
  provides: [ProjectBreakdown dataclass in core/models.py]
  affects: [core/project_breakdown.py (Plan 02), monitoring/orchestrator.py (Plan 03), ui/session_display.py (Plan 04)]
tech_stack:
  added: []
  patterns: [frozen dataclass, Python 3.11+ built-in generics]
key_files:
  created: []
  modified: [core/models.py]
key_decisions:
  - "list[tuple[str, int]] uses Python 3.11+ built-in generics (not typing.List/Tuple) — consistent with requires-python = >=3.11"
  - "No new imports added — dataclass, datetime already present in models.py import block"
  - "Lists are passed at construction time (no field defaults) — frozen dataclasses cannot have mutable defaults"
metrics:
  duration: "< 5 minutes"
  completed: "2026-05-19T20:05:34Z"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 6 Plan 01: ProjectBreakdown Dataclass Summary

**One-liner:** Added `ProjectBreakdown` frozen dataclass with `today`, `billing_month` (list[tuple[str,int]]), and `as_of` (datetime) fields to `core/models.py`.

## What Was Built

`ProjectBreakdown` frozen dataclass appended to `core/models.py` immediately after the `WebUsageData` class. Provides the typed container downstream plans (06-02 through 06-04) depend on for per-project token breakdown results.

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add ProjectBreakdown frozen dataclass to core/models.py | 9adc91b | core/models.py |

## Verification Results

- `from claude_monitor.core.models import ProjectBreakdown` — import OK
- `ProjectBreakdown(today=[('tok', 100)], billing_month=[], as_of=datetime.now(timezone.utc))` — constructs without error
- Mutating a field raises `FrozenInstanceError` — immutability confirmed
- Import block at top of `core/models.py` is unchanged (no new imports added)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — pure in-process data model with no I/O, no external input, no new trust boundaries.

## Self-Check: PASSED

- `core/models.py` modified and committed at 9adc91b
- `class ProjectBreakdown` present at line 135
- `frozen=True` present on both `WebUsageData` and `ProjectBreakdown`
- No file deletions in commit
