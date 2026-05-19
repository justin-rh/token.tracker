---
phase: 01-windows-foundation
plan: "02"
subsystem: data
tags: [python, pathlib, windows, appdata, jsonl, file-locking, utf8]

requires:
  - phase: 01-01
    provides: forked upstream source tree with claude_monitor shim package

provides:
  - Windows-correct JSONL discovery via APPDATA path
  - PermissionError (WinError 32) handling for locked active-session files
  - LOCKED_FILES module-level list for UI "(active session — data not yet visible)" indicator
  - CRLF-safe and BOM-safe JSONL file opens (utf-8-sig, newline='')

affects:
  - 01-03 (requestId deduplication — uses same reader.py pipeline)
  - 01-05 (dashboard UI — reads LOCKED_FILES to display active-session indicator)

tech-stack:
  added: []
  patterns:
    - "Windows path: Path(os.environ['APPDATA']) / '.claude' / 'projects' — never expanduser or Path.home()"
    - "JSONL open: encoding='utf-8-sig', newline='' with line.strip() before json.loads()"
    - "Locked-file signalling: module-level LOCKED_FILES list reset per call, appended on PermissionError"

key-files:
  created: []
  modified:
    - data/reader.py

key-decisions:
  - "Use os.environ['APPDATA'] not Path.home() — APPDATA resolves AppData/Roaming, home() resolves USERPROFILE root (wrong location)"
  - "LOCKED_FILES as module-level list reset at each load_usage_entries() call — simplest interface for UI layer without changing return type signature"
  - "Catch PermissionError before generic Exception in _process_single_file so locked files are recorded rather than reported as errors"
  - "Non-fatal warning printed to stderr when projects directory not found — avoids crash on first run before Claude Code has written any logs"

patterns-established:
  - "PermissionError before Exception: always order except clauses most-specific first in JSONL read loops"
  - "utf-8-sig everywhere: all future JSONL opens must use utf-8-sig + newline='' to handle BOM and CRLF"

requirements-completed:
  - PORT-01

duration: 2min
completed: 2026-05-08
---

# Phase 1 Plan 02: Windows Path Fix and File-Lock Handling Summary

**Windows AppData path replaces Unix expanduser default; PermissionError (WinError 32) caught and recorded in LOCKED_FILES; all JSONL opens hardened with utf-8-sig and newline='' encoding**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-08T17:12:15Z
- **Completed:** 2026-05-08T17:14:40Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- `data/reader.py` now discovers JSONL files at `%APPDATA%\.claude\projects\` — the correct Windows location — instead of the Unix `~/.claude/projects` that silently found zero files
- Active-session files locked by Claude Code (WinError 32) are skipped gracefully; their paths are recorded in the `LOCKED_FILES` module-level list so the UI layer can show the "(active session — data not yet visible)" indicator per D-05
- All JSONL `open()` calls updated to `encoding='utf-8-sig', newline=''` to handle UTF-8 BOM and CRLF line endings without parse errors

## Task Commits

1. **Tasks 02-1 and 02-2: Windows AppData path, PermissionError handling, CRLF-safe opens** - `a9e9cb1` (feat)

**Plan metadata:** *(pending final docs commit)*

## Files Created/Modified

- `data/reader.py` — Added `_get_default_claude_projects_path()` using `os.environ["APPDATA"]`; replaced both `expanduser("~/.claude/projects")` occurrences; added `LOCKED_FILES` module-level list with reset logic; added `except PermissionError` before generic `except Exception` in `_process_single_file` and `load_all_raw_entries`; changed all `open()` calls to `encoding='utf-8-sig', newline=''`; added non-fatal stderr warning when projects directory is missing

## Decisions Made

- Used `os.environ["APPDATA"]` over `Path.home() / "AppData" / "Roaming"` — more explicit, matches D-03 exactly; `Path.home()` resolves to USERPROFILE root (`C:\Users\name`), not AppData\Roaming
- `LOCKED_FILES` as a module-level list (not a return-value addition) to avoid changing the `load_usage_entries` return type signature, which would ripple through callers
- Placed `except PermissionError` before `except Exception` so locked files are silently skipped and recorded rather than appearing as generic read errors in logs

## Deviations from Plan

None — plan executed exactly as written. Both tasks applied atomically to the same file and committed together since the `LOCKED_FILES` variable introduced in task 02-1's scope is immediately used by task 02-2's `except PermissionError` handler.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `data/reader.py` now correctly resolves `C:\Users\<name>\AppData\Roaming\.claude\projects\` on Windows
- PermissionError on the active session file no longer crashes the monitor
- `data.reader.LOCKED_FILES` is available for the UI layer to render the active-session indicator (Plan 05)
- Plan 01-03 (requestId deduplication) can proceed — it modifies the same `_process_single_file` pipeline

---
*Phase: 01-windows-foundation*
*Completed: 2026-05-08*
