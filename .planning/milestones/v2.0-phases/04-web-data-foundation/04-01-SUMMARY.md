---
phase: 04-web-data-foundation
plan: "01"
subsystem: dependencies, models
tags: [keyring, browser-cookie3, httpx, dataclass, frozen, WebUsageData]

# Dependency graph
requires:
  - phase: 03-overage-pool-dashboard
    provides: core/models.py with SessionBlock, ThresholdState, PoolState frozen dataclass patterns
provides:
  - keyring>=25.0.0 installed (Windows Credential Manager API)
  - browser-cookie3>=0.19.1 installed (Firefox/Chrome cookie extraction)
  - httpx>=0.27.0 installed (HTTP client for claude.ai API)
  - WebUsageData frozen dataclass in core/models.py (return type for fetch_web_usage())
affects:
  - 04-02 (usage_fetcher.py uses WebUsageData as return type)
  - 04-03 (web_poller.py depends on WebUsageData)
  - 04-04 (orchestrator wire-up references WebUsageData)
  - 04-05 (session_display.py renders WebUsageData fields)
  - 04-06 (cli/main.py receives WebUsageData from WebPoller)

# Tech tracking
tech-stack:
  added:
    - keyring 25.7.0 (Windows Credential Manager storage)
    - browser-cookie3 0.20.1 (browser cookie extraction)
    - httpx 0.28.1 (async-capable HTTP client)
  patterns:
    - frozen dataclass for immutable value objects (established in Phase 3, extended here)

key-files:
  created: []
  modified:
    - pyproject.toml (added three Phase 4 deps with group comment)
    - core/models.py (added WebUsageData frozen dataclass before normalize_model_name)

key-decisions:
  - "curl_cffi deferred per D-21 — Cloudflare does NOT block httpx on this machine (confirmed by spike 2026-05-18)"
  - "plan_limit_tokens is Optional[int] — None for Teams accounts where monthly_limit field is in cents not tokens"
  - "WebUsageData inserted after SessionBlock, before normalize_model_name() — consistent with existing class order"

patterns-established:
  - "frozen dataclass pattern: @dataclass(frozen=True) for all immutable value objects (ThresholdState, PoolState, WebUsageData)"
  - "Phase N additions grouped with comment in pyproject.toml dependencies block"

requirements-completed: [WEBD-01, WEBD-02, WEBD-03, AUTH-01, AUTH-02]

# Metrics
duration: 13min
completed: 2026-05-18
---

# Phase 4 Plan 01: Dependencies + WebUsageData Frozen Dataclass Summary

**keyring 25.7.0, browser-cookie3 0.20.1, and httpx 0.28.1 installed; WebUsageData frozen dataclass added to core/models.py as the authoritative return type for fetch_web_usage()**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-18T23:26:22Z
- **Completed:** 2026-05-18T23:39:29Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added three Phase 4 package dependencies to pyproject.toml and confirmed all are importable
- Added WebUsageData frozen dataclass to core/models.py with all four required fields (utilization_pct, reset_at, fetched_at, plan_limit_tokens)
- Confirmed immutability: FrozenInstanceError raised on mutation attempt

## Task Commits

Each task was committed atomically:

1. **Task 1: Add keyring, browser-cookie3, httpx to pyproject.toml** - `3b6a45a` (chore)
2. **Task 2: Add WebUsageData frozen dataclass to core/models.py** - `0496092` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `pyproject.toml` - Added keyring>=25.0.0, browser-cookie3>=0.19.1, httpx>=0.27.0 under "# Phase 4 additions:" comment
- `core/models.py` - Added WebUsageData frozen dataclass between SessionBlock and normalize_model_name()

## Decisions Made

- curl_cffi was explicitly NOT added (deferred per D-21 — Cloudflare not blocking httpx on this machine per spike)
- plan_limit_tokens typed as Optional[int] to handle Teams accounts where the API's monthly_limit is in cents (not tokens), making a token-count value meaningless
- WebUsageData uses `frozen=True` to match the established pattern from ThresholdState and PoolState

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three new packages are importable from the project environment
- WebUsageData is the return type for `fetch_web_usage()` which is implemented in 04-02
- 04-02 can now import WebUsageData from core.models and proceed with cookie extraction and HTTP fetch logic

---
*Phase: 04-web-data-foundation*
*Completed: 2026-05-18*
