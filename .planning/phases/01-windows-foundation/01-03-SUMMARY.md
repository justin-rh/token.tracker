---
phase: 1
plan: 3
subsystem: data-pipeline
tags: [deduplication, requestId, token-counting, correctness]
dependency_graph:
  requires: [01-02]
  provides: [correct-token-counts]
  affects: [data/reader.py, all token totals displayed in UI]
tech_stack:
  added: []
  patterns: [max-output_tokens per requestId, collect-then-dedup before mapping]
key_files:
  created:
    - tests/__init__.py
    - tests/test_deduplication.py
  modified:
    - data/reader.py
decisions:
  - "Collect all raw JSONL lines per file first, then deduplicate, then map — ensures max(output_tokens) selection works across the full set of streaming chunks"
  - "New _deduplicate_entries() function placed immediately after LOCKED_FILES declaration — before any processing logic, visually obvious as a pre-processing step"
  - "Existing _create_unique_hash() / processed_hashes dedup left in place as a secondary guard against cross-file message_id duplicates (different concern from requestId streaming dedup)"
metrics:
  duration: "8 min"
  completed: "2026-05-08T17:19:00Z"
  tasks_completed: 2
  files_modified: 1
  files_created: 2
---

# Phase 1 Plan 3: requestId Deduplication Summary

**One-liner:** requestId dedup via max(output_tokens) per request collapses 2-10 streaming placeholder entries to one correct final entry, fixing 100-174x token count inflation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 03-1 | Implement requestId deduplication in data/reader.py | 61b64f7 | data/reader.py |
| 03-2 | Write deduplication unit test with known fixture data | 64566c0 | tests/__init__.py, tests/test_deduplication.py |

## What Was Built

### `_deduplicate_entries()` function (data/reader.py)

Added a new function immediately after the `LOCKED_FILES` declaration. It:
- Groups raw JSONL entry dicts by `requestId` (checks both `entry["requestId"]` and `entry["request_id"]`)
- For each group, retains only the entry with the highest `output_tokens` value (the final streaming chunk)
- Passes entries without a `requestId` through unchanged (tool-use results, system messages)

### Refactored `_process_single_file()` (data/reader.py)

Changed the processing flow from line-by-line to collect-then-dedup:
1. Read all lines from the JSONL file into `raw_parsed` list
2. Call `_deduplicate_entries(raw_parsed)` to produce `deduped_parsed`
3. Iterate over `deduped_parsed` for `_should_process_entry` + `_map_to_usage_entry`

This ensures deduplication happens on the complete set of entries for a file, before any token extraction.

### Unit tests (tests/test_deduplication.py)

5 pytest tests covering:
- `test_single_entry_passthrough` — no-op when no duplicates
- `test_duplicates_collapsed_to_highest_output` — 5 streaming entries → 1 final (output_tokens=347)
- `test_multiple_requests_each_deduplicated` — 2 requestIds → 2 correct entries
- `test_entries_without_request_id_preserved` — tool-use entries pass through
- `test_inflation_ratio` — proves 10+1=11 raw → 1 deduped, raw_total=357 vs deduped_total=347

All 5 passed: `5 passed in 0.07s`

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Dedup function present (≥2 matches) | `grep -n "_deduplicate_entries\|dedup" data/reader.py` | 7 matches |
| requestId referenced | `grep "requestId\|request_id" data/reader.py` | 14 matches |
| All 5 tests pass | `python -m pytest tests/test_deduplication.py -v` | 5 passed |
| Import clean | `python -c "from data.reader import _deduplicate_entries; print('OK')"` | OK |

## Deviations from Plan

None — plan executed exactly as written. The existing `_create_unique_hash()` / `processed_hashes` mechanism was left in place; it deduplicates by `message_id:request_id` composite key across files, which is a different (complementary) concern from the per-file streaming requestId dedup.

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- `data/reader.py` — modified, verified via import and grep
- `tests/__init__.py` — created, present at expected path
- `tests/test_deduplication.py` — created, all 5 tests pass
- Commit 61b64f7 exists: `feat(01-03): add requestId deduplication to data/reader.py`
- Commit 64566c0 exists: `test(01-03): add deduplication unit tests with fixture data`
