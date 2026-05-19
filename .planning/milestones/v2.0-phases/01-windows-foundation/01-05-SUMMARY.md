---
phase: 01-windows-foundation
plan: "05"
subsystem: ui
tags: [rich, shutil, ctypes, utf-8, vtp, windows-terminal, active-session]

# Dependency graph
requires:
  - phase: 01-02
    provides: LOCKED_FILES module-level list exposed from data.reader for active-session detection
  - phase: 01-03
    provides: Correct deduplicated token counts visible in dashboard
  - phase: 01-04
    provides: Accurate statusline.jsonl cost figures visible in dashboard

provides:
  - Rich Console() instantiated with explicit width=shutil.get_terminal_size().columns (120 fallback)
  - _get_console_width() helper in terminal/themes.py
  - Active-session locked-file indicator rendered in dim yellow when LOCKED_FILES is non-empty
  - Python 3.12 compatible claude_monitor/ shim (find_spec replaces dropped find_module)
  - Human-verified smoke test: all 5 Phase 1 success criteria passed

affects:
  - Phase 2 (Threshold Detection) — dashboard foundation confirmed working end-to-end
  - Phase 3 (Overage Pool Dashboard) — UI layer stable; width/color/refresh patterns established

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_get_console_width() in terminal/themes.py — always pass explicit width to Console(); never rely on Rich auto-detection on Windows"
    - "LOCKED_FILES sentinel pattern — UI layer reads data.reader.LOCKED_FILES after each render cycle to show active-session indicator"
    - "VTP + UTF-8 bootstrap in monitor.py — runs before any Rich imports; safe no-op on Windows Terminal"

key-files:
  created: []
  modified:
    - terminal/themes.py
    - ui/display_controller.py
    - claude_monitor/__init__.py

key-decisions:
  - "[01-05] _get_console_width() added to terminal/themes.py rather than inline in display_controller.py — centralizes fallback logic for all Console() instantiations"
  - "[01-05] Python 3.12 shim fix: claude_monitor/__init__.py updated to use importlib.util.find_spec instead of find_module (silently dropped in 3.12) — required for import system to work on Python 3.12+"
  - "[01-05] VTP and UTF-8 setup confirmed already present in monitor.py from Plan 01-01; no duplicate setup needed"
  - "[01-05] Active-session indicator uses dim yellow styling — informational, not alarming"

patterns-established:
  - "Console width pattern: Always use _get_console_width() → shutil.get_terminal_size().columns with 120 fallback; never use Console() without explicit width on Windows"
  - "Locked file indicator: Read data.reader.LOCKED_FILES in UI render path; render dim yellow note when non-empty"

requirements-completed: [PORT-04, DISP-01]

# Metrics
duration: ~15min
completed: 2026-05-08
---

# Phase 1 Plan 05: Rich Display Fix and End-to-End Smoke Test Summary

**Explicit Rich Console width via shutil.get_terminal_size(), active-session locked-file indicator, Python 3.12 shim fix — human smoke test confirmed all 5 Phase 1 success criteria pass**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-08
- **Completed:** 2026-05-08
- **Tasks:** 2 (1 code, 1 human-verify)
- **Files modified:** 3

## Accomplishments

- Dashboard now renders at full terminal width — explicit width=_get_console_width() passed to all Console() instantiations; no more 80-column cap
- Active-session indicator shows "(active session — data not yet visible: N file(s) locked by Claude Code)" in dim yellow when LOCKED_FILES is non-empty, wiring Plan 01-02's LOCKED_FILES sentinel into the UI layer
- Python 3.12 compatibility restored: claude_monitor/__init__.py shim updated from deprecated find_module to find_spec API; the old API was silently dropped in Python 3.12 causing silent import failures
- Human smoke test approved: all five Phase 1 success criteria confirmed — session data visible, sane token counts, non-zero cost, full terminal width, in-place refresh without scrolling

## Task Commits

Each task was committed atomically:

1. **Task 05-1: Fix Console width and add active-session indicator** - `766768a` (feat)
2. **Task 05-1 (deviation): Python 3.12 shim fix** - `7cf8a76` (fix)

## Files Created/Modified

- `terminal/themes.py` — Added `_get_console_width()` using `shutil.get_terminal_size().columns` with 120 fallback; all `Console()` instantiations pass explicit width
- `ui/display_controller.py` — Imports `LOCKED_FILES` from `data.reader`; renders active-session indicator in dim yellow when files are locked
- `claude_monitor/__init__.py` — Fixed meta-path shim to use `importlib.util.find_spec` (Python 3.12 compatible); `find_module` was silently dropped in 3.12

## Decisions Made

- Placed `_get_console_width()` in `terminal/themes.py` rather than inline in `display_controller.py` to centralize the fallback logic for all Console() uses across the project
- Used `find_spec` over `find_module` in the shim: Python 3.12 removed `find_module` from the import system without deprecation warning; `find_spec` is the correct replacement and is backward-compatible to Python 3.4+
- VTP and UTF-8 setup was already present in `monitor.py` from Plan 01-01; confirmed existing code is correct and no duplication was added

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.12 claude_monitor/ shim used removed find_module API**
- **Found during:** Task 05-1 (Console width fix and active-session indicator)
- **Issue:** `claude_monitor/__init__.py` contained a meta-path finder using `find_module()`, which was silently dropped in Python 3.12. On Python 3.12+ the shim was effectively a no-op, causing all `claude_monitor.*` imports to fail silently
- **Fix:** Updated the meta-path finder to implement `find_spec()` instead of `find_module()`; the new implementation returns a `ModuleSpec` pointing to the real module, which is the correct Python 3.12+ contract
- **Files modified:** `claude_monitor/__init__.py`
- **Verification:** `python -c "import claude_monitor; print('OK')"` exits 0
- **Committed in:** `7cf8a76`

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix was required for correct operation on Python 3.12+. No scope creep.

## Issues Encountered

- VTP (`SetConsoleMode`) and UTF-8 (`io.TextIOWrapper`) bootstrap were already present in `monitor.py` from Plan 01-01 execution. The plan instructed adding them but they were not missing — no duplicate setup was added. Verified via grep before making any edits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 1 is complete. All 5 success criteria confirmed by human smoke test:
  1. Session data visible from `%APPDATA%\.claude\projects\`
  2. Token counts sane (no 100x inflation)
  3. Cost figures non-zero and sourced from statusline.jsonl
  4. Dashboard renders at full terminal width
  5. Live updates in-place without scrolling
- Phase 2 (Threshold Detection) can begin: P90 detection against the now-confirmed accurate data pipeline
- No blockers for Phase 2

## Self-Check: PASSED

- `766768a` found in git log: confirmed
- `7cf8a76` found in git log: confirmed
- `terminal/themes.py` modified: confirmed
- `ui/display_controller.py` modified: confirmed
- `claude_monitor/__init__.py` modified: confirmed

---
*Phase: 01-windows-foundation*
*Completed: 2026-05-08*
