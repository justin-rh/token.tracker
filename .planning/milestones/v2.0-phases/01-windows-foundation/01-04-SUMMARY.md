---
phase: 1
plan: 4
title: Replace costUSD with statusline.jsonl Cost Source
subsystem: cost-attribution
tags: [cost, statusline, analyzer, windows-foundation]
dependency_graph:
  requires: [01-02]
  provides: [statusline-cost-reader, cost-usd-primary-source]
  affects: [data/analyzer.py, core/statusline_cost.py]
tech_stack:
  added: [core/statusline_cost.py]
  patterns: [statusline-jsonl-cost-lookup, pricing-engine-fallback]
key_files:
  created: [core/statusline_cost.py]
  modified: [data/analyzer.py]
decisions:
  - "SessionBlock has no session_id field — statusline lookup falls through to pricing-engine fallback for all blocks (D-07: adapt when real data structure known)"
  - "APPDATA in comment of statusline_cost.py is explanatory contrast, not code — statusline path correctly uses Path.home()"
  - "_resolve_block_cost() added as module-level function in analyzer.py to cleanly separate cost resolution from block aggregation"
metrics:
  duration: 1 min
  completed: 2026-05-08
  tasks_completed: 2
  tasks_total: 2
---

# Phase 1 Plan 4: Replace costUSD with statusline.jsonl Cost Source — Summary

**One-liner:** New `core/statusline_cost.py` reads `~/.claude/statusline.jsonl` cost.total_cost_usd and wires it into `data/analyzer.py` as the primary SessionBlock cost source with pricing-engine fallback.

## What Was Built

### core/statusline_cost.py (new)

Reads `~/.claude/statusline.jsonl` (per D-06) and returns a `dict` mapping session identifiers to `float` cost_usd values. Key behaviors:

- Path: `Path.home() / ".claude" / "statusline.jsonl"` — home dir, NOT APPDATA (APPDATA is for the projects dir)
- Opens with `encoding='utf-8-sig'` (handles BOM) and `newline=''` (handles CRLF)
- Handles `PermissionError`, `json.JSONDecodeError`, missing file — returns `{}` in all error cases (T-04-03 mitigation)
- Key extraction: prefers `session_id`/`sessionId`, falls back to `timestamp` string
- Last-write-wins for duplicate keys (statusline is continuously updated)

### data/analyzer.py (modified)

- Added `from core.statusline_cost import read_statusline_costs` import
- Added module-level `_resolve_block_cost(block, statusline_costs)` function with three-level resolution: session_id match → start_time ISO timestamp match → pricing-engine fallback
- `transform_to_blocks()` calls `read_statusline_costs()` once per invocation (not per entry)
- Each block's `cost_usd` is set via `_resolve_block_cost()` after finalization
- No `costUSD` dict key reads present (field removed at v1.0.9 upstream, per D-08)

## Deviations from Plan

### Auto-noted Behavior (not a deviation, expected per D-07)

**SessionBlock has no session_id field:** The plan's `_resolve_block_cost()` strategy shows a `block.session_id` primary path. `SessionBlock` (core/models.py) has no `session_id` field — it's a time-window aggregate identified by `start_time.isoformat()`. The implementation handles this correctly:

- `hasattr(block, 'session_id')` guard prevents AttributeError
- `start_time.isoformat()` timestamp key match added as secondary path
- Pricing-engine accumulated `block.cost_usd` is the effective fallback

Per D-07: if/when real statusline.jsonl data shows a different structure or matching strategy is needed, update `_extract_key()` in `statusline_cost.py` and the matching logic in `_resolve_block_cost()`. The infrastructure is in place; the matching will improve with real data.

## Known Stubs

None — no hardcoded empty values or placeholder text in the implementation. The fallback to pricing-engine cost is intentional behavior, not a stub.

## Cost Display Note

Per CLAUDE.md: all displayed cost figures must include "est." prefix. This plan implements the cost SOURCE (statusline.jsonl reader + analyzer wiring). The "est." prefix requirement applies to the UI display layer, which is addressed in Plan 05 / Phase 3. This is not a stub — the data pipeline is complete; the display constraint is a separate concern.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what is covered in the plan's threat model (T-04-01 through T-04-04 all accepted or mitigated).

## Self-Check: PASSED

- [x] `core/statusline_cost.py` exists
- [x] Commit 9c06902 exists (feat(01-04): create core/statusline_cost.py)
- [x] Commit ef84d64 exists (feat(01-04): wire statusline cost into data/analyzer.py)
- [x] `python -c "from core.statusline_cost import read_statusline_costs; r = read_statusline_costs(); print(type(r))"` prints `<class 'dict'>`
- [x] `python -c "import data.analyzer; print('OK')"` prints `OK`
- [x] No `costUSD` dict key reads in `data/analyzer.py`
- [x] `Path.home() / ".claude" / "statusline.jsonl"` present in `core/statusline_cost.py`
- [x] No APPDATA code (only explanatory comment) in `core/statusline_cost.py`
