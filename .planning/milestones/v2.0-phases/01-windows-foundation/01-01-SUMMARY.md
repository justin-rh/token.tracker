---
phase: 01-windows-foundation
plan: "01"
subsystem: infra
tags: [python, rich, upstream-fork, claude-monitor, pyproject, windows]

# Dependency graph
requires: []
provides:
  - "Upstream claude_monitor source modules at repo root (data/, core/, monitoring/, ui/, cli/, terminal/, utils/)"
  - "Root-level monitor.py entry point with Windows UTF-8 and VTP setup"
  - "pyproject.toml with name=token-tracker, version=0.1.0, tzdata dependency"
  - "claude_monitor/ shim package enabling upstream internal imports"
  - "python monitor.py --help exits 0 with full argument list"
affects:
  - "02-windows-foundation"
  - "03-windows-foundation"
  - "04-windows-foundation"
  - "05-windows-foundation"

# Tech tracking
tech-stack:
  added:
    - "rich>=13.7.0 — terminal UI library"
    - "pydantic>=2.0.0 — data validation"
    - "pydantic-settings>=2.0.0 — settings management"
    - "numpy>=1.21.0 — P90 calculation"
    - "pytz>=2023.3 — timezone handling"
    - "tzdata — Windows IANA timezone database"
    - "pyyaml>=6.0 — YAML config support"
  patterns:
    - "claude_monitor/ shim package pattern: aliases flat repo-root modules under claude_monitor.* namespace so upstream internal imports resolve without patching source files"
    - "monitor.py as root entry point: Windows UTF-8 reconfiguration then delegate to cli.main:main()"

key-files:
  created:
    - "monitor.py — root entry point with Windows UTF-8/VTP setup, delegates to cli.main:main()"
    - "pyproject.toml — token-tracker package metadata, tzdata dep, scripts entry"
    - "claude_monitor/__init__.py — shim package aliasing flat modules under claude_monitor.* namespace"
    - "data/reader.py — upstream JSONL reader (verbatim copy)"
    - "core/pricing.py — upstream pricing engine (verbatim copy)"
    - "monitoring/orchestrator.py — upstream monitoring orchestrator (verbatim copy)"
    - "ui/display_controller.py — upstream Rich display controller (verbatim copy)"
    - "_upstream_main.py — upstream __main__.py for reference"
    - "_version.py — upstream version string (0.1.0 in pyproject.toml)"
    - "error_handling.py — upstream error handling module"
  modified: []

key-decisions:
  - "claude_monitor/ shim package created at repo root to alias flat module dirs under claude_monitor.* namespace — avoids patching 40+ upstream source files that use from claude_monitor.xxx import yyy"
  - "monitor.py delegates to cli.main:main() — clean separation, upstream CLI parser (argparse via pydantic-settings) remains unchanged"
  - "Windows VTP (Virtual Terminal Processing) enabled via ctypes in monitor.py — needed for ANSI color in cmd.exe"
  - "Dependencies installed to system Python 3.12.10 — no venv created in this plan (Phase 1 baseline)"

patterns-established:
  - "Namespace shim pattern: when upstream uses a package namespace (claude_monitor.*) and code lives flat at repo root, create a shim __init__.py that sys.modules-aliases the flat modules"
  - "monitor.py entry point always does Windows encoding setup before any Rich imports"

requirements-completed:
  - PORT-01
  - DISP-01

# Metrics
duration: 5min
completed: 2026-05-08
---

# Phase 1 Plan 01: Fork Upstream and Bootstrap Project Structure Summary

**Upstream claude_monitor v3.1.0 forked to repo root with claude_monitor shim package; python monitor.py --help works on Windows Python 3.12**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-08T17:03:48Z
- **Completed:** 2026-05-08T17:09:00Z
- **Tasks:** 2
- **Files modified:** 45

## Accomplishments

- Cloned github.com/Maciek-roboblog/Claude-Code-Usage-Monitor v3.1.0 to /c/tmp/upstream-ccum; copied all source modules (data/, core/, monitoring/, ui/, cli/, terminal/, utils/) to repo root
- Created `claude_monitor/` shim package that registers flat module dirs under the `claude_monitor.*` namespace so all upstream internal `from claude_monitor.xxx import yyy` statements resolve without patching any source files
- Created `monitor.py` root entry point with Windows UTF-8 stdout/stderr reconfiguration and VTP enablement before any Rich imports; `python monitor.py --help` exits 0 with full argument list
- Created `pyproject.toml` with `name = "token-tracker"`, `version = "0.1.0"`, `requires-python = ">=3.11"`, `tzdata` dependency, and `token-tracker = "monitor:main"` script entry

## Task Commits

Each task was committed atomically:

1. **Task 01-1: Clone upstream and copy source files to repo root** - `6def8ef` (feat)
2. **Task 01-2: Create pyproject.toml and monitor.py entry point** - `5166033` (feat)

**Plan metadata:** (see below — committed with SUMMARY.md)

## Files Created/Modified

- `monitor.py` — root entry point; Windows UTF-8/VTP setup + delegates to cli.main:main()
- `pyproject.toml` — token-tracker package metadata with tzdata and scripts entry
- `claude_monitor/__init__.py` — shim package aliasing flat dirs under claude_monitor.* namespace
- `data/reader.py, data/aggregator.py, data/analyzer.py, data/analysis.py` — upstream JSONL data pipeline
- `core/pricing.py, core/calculations.py, core/plans.py, core/settings.py, core/models.py, core/p90_calculator.py, core/data_processors.py` — upstream core logic
- `monitoring/orchestrator.py, monitoring/data_manager.py, monitoring/session_monitor.py` — upstream monitoring layer
- `ui/display_controller.py, ui/components.py, ui/layouts.py, ui/progress_bars.py, ui/session_display.py, ui/table_views.py` — upstream Rich UI
- `cli/main.py, cli/bootstrap.py` — upstream CLI entry logic
- `terminal/manager.py, terminal/themes.py` — upstream terminal management
- `utils/formatting.py, utils/model_utils.py, utils/notifications.py, utils/time_utils.py, utils/timezone.py` — upstream utilities
- `error_handling.py, _version.py, _upstream_main.py, _upstream_init.py` — upstream root-level modules
- `.gitignore` — excludes __pycache__, .venv, dist, build artifacts

## Decisions Made

- **claude_monitor shim package**: The upstream uses `src/claude_monitor/` layout with all internal imports as `from claude_monitor.xxx import yyy`. Per D-01, files live flat at repo root. Creating a `claude_monitor/__init__.py` shim that registers sys.modules aliases lets upstream code work without patching 40+ files. This is the zero-diff approach.
- **ctypes VTP enablement**: Added `SetConsoleMode` call in monitor.py (per PITFALLS.md recommendation) to ensure ANSI escape codes render in cmd.exe/legacy terminals.
- **Dependencies installed to system Python**: No venv created in this plan. Phase 1 baseline; future plans can set up venv if needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Created claude_monitor/ namespace shim**
- **Found during:** Task 01-1 (after discovering upstream uses src/claude_monitor/ layout)
- **Issue:** Plan expected upstream to use flat package dirs; actual layout is src/claude_monitor/ with all internal imports as `from claude_monitor.xxx`. Without a shim, all upstream imports would fail with ModuleNotFoundError.
- **Fix:** Created `claude_monitor/__init__.py` that registers sys.modules aliases mapping `claude_monitor.xxx` to the flat repo-root modules.
- **Files modified:** `claude_monitor/__init__.py` (new)
- **Verification:** `python -c "from cli.main import main"` succeeds; `python monitor.py --help` exits 0.
- **Committed in:** 6def8ef (Task 01-1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The shim is required for correctness — without it, no upstream module can be imported. No scope creep; addresses the exact problem the task identified.

## Issues Encountered

- Upstream src/ layout (src/claude_monitor/) required creating the claude_monitor/ shim to preserve all upstream import paths — resolved via namespace aliasing in sys.modules.
- rich and other dependencies not installed in system Python — installed via `pip install rich pydantic pydantic-settings pyyaml pytz numpy tzdata` as part of task execution.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All upstream source modules are importable from repo root
- `python monitor.py --help` exits 0
- Ready for Plan 02: Windows path fix (data/reader.py path resolution) and JSONL deduplication
- No blockers

## Self-Check: PASSED

- monitor.py: FOUND
- pyproject.toml: FOUND
- 01-01-SUMMARY.md: FOUND
- commit 6def8ef (task 01-1): FOUND
- commit 5166033 (task 01-2): FOUND
- commit e5fc486 (metadata): FOUND
- python monitor.py --help: exits 0

---
*Phase: 01-windows-foundation*
*Completed: 2026-05-08*
