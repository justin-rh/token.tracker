---
phase: 04-web-data-foundation
plan: "02"
subsystem: core/usage_fetcher
tags: [auth, keyring, firefox-cookies, web-api, httpx]
dependency_graph:
  requires:
    - 04-01  # WebUsageData dataclass in core/models.py; keyring/httpx/browser-cookie3 deps
  provides:
    - fetch_web_usage  # authoritative utilization % from claude.ai API
    - _discover_org_id  # GET /api/account → first membership UUID
    - _migrate_config_to_keyring  # D-04 one-way migration on startup
    - _read_auth_cookies  # refactored: keyring(1) > Firefox(2) > Chrome(3) per D-06
  affects:
    - 04-03  # WebPoller calls fetch_web_usage() from this plan
    - 04-06  # cli/main.py calls _migrate_config_to_keyring() and _read_auth_cookies() from this plan
tech_stack:
  added:
    - keyring  # Windows Credential Manager read/write
    - httpx    # sync HTTP client for fetch_web_usage() and _discover_org_id()
    - browser-cookie3  # Firefox cookie extraction (already added in 04-01 pyproject.toml)
  patterns:
    - Auth priority chain: keyring > Firefox > Chrome > manual (D-06)
    - Atomic config.json write: .tmp → .replace() pattern for migration
    - Graceful degradation: all auth and HTTP failures return None, never raise
    - Account type branch: five_hour (Max/Pro) vs extra_usage (Teams/Enterprise)
key_files:
  modified:
    - core/usage_fetcher.py  # added 5 functions, refactored _read_auth_cookies()
  created:
    - tests/test_usage_fetcher_web.py  # 13 unit tests, all offline (mocked httpx)
decisions:
  - D-06 auth priority implemented: keyring(1) > Firefox(2) > Chrome(3)
  - D-04 migration implemented: session_key/cf_clearance moved from config.json to keyring atomically
  - D-22 JSON access: all response fields use .get() with defaults
  - Security: sessionKey value never logged at any level; source only ("from keyring", "from Firefox")
  - five_hour.utilization assumed 0-100 scale (only seen 0.0 in spike); comment added with ASSUMED tag
  - Teams reset_at derived from billing_cycle_start_day in config.json (no API resets_at for Teams)
  - fetch_pool_spend_usd() preserved unchanged (uses urllib.request, not httpx)
metrics:
  duration_seconds: 327
  completed_date: "2026-05-18"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
  files_created: 1
  tests_added: 13
  tests_passing: 13
---

# Phase 4 Plan 02: usage_fetcher.py Refactor — Auth + Web Usage Fetch Summary

**One-liner:** Firefox+keyring auth priority chain (D-06), keyring migration (D-04), fetch_web_usage() with Teams/Max account branching via httpx, and 13 offline unit tests.

## What Was Built

### Task 1: _read_firefox_cookies(), _migrate_config_to_keyring(), _read_auth_cookies() refactor

`_read_firefox_cookies()` wraps `browser_cookie3.firefox(domain_name=".claude.ai")` in a full `try/except Exception` so Firefox WAL locks and missing profiles silently return `(None, None)`. Logs source but never cookie values.

`_migrate_config_to_keyring()` reads `session_key` and `cf_clearance` from `config.json`, calls `keyring.set_password("claude-monitor", ...)` for each found value, deletes them from the config dict, and writes back atomically using the `.tmp → .replace()` pattern. No-op when file missing or neither key present.

`_read_auth_cookies()` body replaced entirely with the D-06 priority chain:
1. `keyring.get_password("claude-monitor", "sessionKey") or None` — returns immediately if found
2. `_read_firefox_cookies()` — returns immediately if sessionKey found
3. `_read_chrome_cookies()` — existing implementation, unchanged, now at position 3

Security enforcement: only logs source string ("from keyring", "from Firefox", "from Chrome") — never the actual key value at any log level.

### Task 2: _discover_org_id(), _derive_billing_cycle_reset(), fetch_web_usage() + unit tests

`_discover_org_id(session_key)` calls `GET https://claude.ai/api/account` via httpx, iterates `memberships[]`, returns the first `organization.uuid` or None. Logs "discovered org_id (omitted from log)" — UUID not written to log.

`_derive_billing_cycle_reset(config_dir)` reads `billing_cycle_start_day` from config.json (defaults to 1) and computes the next UTC datetime when that day occurs.

`fetch_web_usage(org_id, config_dir)` branches on account type:
- `five_hour is not None` → Max/Pro: reads `five_hour.utilization` (ASSUMED 0-100 scale) and `five_hour.resets_at`
- `extra_usage and extra_usage.get("is_enabled")` → Teams/Enterprise: reads `extra_usage.utilization`, derives reset_at from billing cycle config
- Both null/disabled → returns None

Returns None gracefully on 401, 403, network exceptions, missing sessionKey, disabled extra_usage, or both null fields. Never raises.

`tests/test_usage_fetcher_web.py` — 13 unit tests, all offline (httpx mocked at module level):
- Teams branch, Max/Pro branch, 401, 403, network error, no sessionKey, disabled extra_usage, both null
- Auth priority: keyring wins (Firefox+Chrome never called), Firefox wins (Chrome never called)
- Migration: session_key migrated+deleted, no-op when absent, no-op when file missing

## Deviations from Plan

None — plan executed exactly as written. All functions implemented per spec with exact code from the plan's `<action>` blocks.

## Known Stubs

None. `fetch_web_usage()` returns real `WebUsageData` from the live API; no hardcoded placeholders. The `plan_limit_tokens=None` for Teams accounts is documented behavior (monthly_limit is in cents, not tokens) per the plan spec.

## Threat Flags

No new security surface beyond what was planned.

| Threat | Mitigation Applied |
|--------|-------------------|
| T-04-02-01: sessionKey logging | All log calls verified — source string only, never key value |
| T-04-02-02: config.json plaintext | _migrate_config_to_keyring() deletes session_key after copying to keyring; atomic write |
| T-04-02-04: API JSON injection | All field access uses .get() with defaults; no eval/exec |
| T-04-02-06: org_id in logs | _discover_org_id() logs "omitted from log" text, not UUID |
| T-04-02-07: Firefox WAL lock | _read_firefox_cookies() catches Exception; falls through to Chrome silently |

## Self-Check

### Files exist:
- `core/usage_fetcher.py` — FOUND
- `tests/test_usage_fetcher_web.py` — FOUND

### Commits exist:
- `5a7eb12` — Task 1 (Firefox cookies, keyring migration, _read_auth_cookies refactor)
- `e767193` — Task 2 (_discover_org_id, _derive_billing_cycle_reset, fetch_web_usage, tests)

### Tests:
- `python -m pytest tests/test_usage_fetcher_web.py -v` → 13 passed, 0 failed

## Self-Check: PASSED
