---
phase: 04-web-data-foundation
fixed_at: 2026-05-19T00:00:00Z
review_path: .planning/phases/04-web-data-foundation/04-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 5
skipped: 1
status: partial
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-05-19
**Source review:** `.planning/phases/04-web-data-foundation/04-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 5
- Skipped: 1

## Fixed Issues

### CR-01: `fetch_pool_spend_usd()` uses `urllib.request.urlopen()` without SSL bypass

**Files modified:** `core/usage_fetcher.py`
**Commit:** e199be4
**Applied fix:** Replaced `urllib.request` import and `urlopen()` call with `httpx.get(..., verify=False)` + `resp.raise_for_status()` + `resp.json()`. Removed the `import urllib.request` inline import. The function now matches the SSL bypass pattern used by `fetch_web_usage()` and `_discover_org_id()`.

---

### WR-01: `_setup_auth()` infinite loop — no escape when user repeatedly presses Enter

**Files modified:** `cli/main.py`
**Commit:** cca3abf
**Applied fix:** Replaced `while True:` with `MAX_AUTH_ATTEMPTS = 3; attempts = 0; while attempts < MAX_AUTH_ATTEMPTS:` and increments `attempts = attempts + 1` at the top of each iteration. Added a fallback `return None, cfg.get("org_id")` after the loop exits, with a warning log message. All existing return paths (success, EOFError/KeyboardInterrupt, successful paste) are preserved unchanged.

---

### WR-02: `fetch_web_usage()` logs full raw API response at DEBUG level

**Files modified:** `core/usage_fetcher.py`
**Commit:** e073cca
**Applied fix:** Replaced `logger.debug("fetch_web_usage: raw response: %s", body)` with a structural shape log that emits only `list(body.keys())`, a boolean for `five_hour` presence, and a boolean for `extra_usage_enabled`. No billing data or PII is included in the log output.

---

### WR-03: `_write_pool_spend_cache()` writes naive (timezone-unaware) `last_updated` timestamp

**Files modified:** `core/pool_state_manager.py`
**Commit:** f0b3784
**Applied fix:** Changed `datetime.now().isoformat()` to `datetime.now(timezone.utc).isoformat()`. The `timezone` symbol was already imported at the top of the file (`from datetime import date, datetime, timezone`), so no import change was needed.

---

### WR-05: `fetch_web_usage()` missing test for `five_hour.resets_at` absent path

**Files modified:** `tests/test_usage_fetcher_web.py`
**Commit:** 28ed529
**Applied fix:** Added `test_fetch_web_usage_five_hour_no_resets_at_falls_back()` at the end of the test file under a new section header. The test supplies a response with `five_hour.utilization=30.0` but no `resets_at` key, then asserts `result.utilization_pct == 30.0`, `result.reset_at is not None`, and `result.reset_at.tzinfo is not None`. Mock paths use `core.usage_fetcher` consistent with the rest of the test file (source-tree mode).

---

## Skipped Issues

### WR-04: Test mock path targets `core.usage_fetcher.httpx` — wrong import path for installed package

**File:** `tests/test_usage_fetcher_web.py:51`
**Reason:** skipped: code context differs from review — patch paths are correct for the actual project layout. The `core` directory is a top-level package at the project root (listed directly in `[tool.setuptools.packages.find]` alongside `claude_monitor`). The `claude_monitor` directory contains only `__init__.py` and has no `core` subpackage. Changing patch targets to `claude_monitor.core.usage_fetcher` would immediately break all tests because that module path does not exist. The existing `core.usage_fetcher` patch targets are consistent with the test imports (`from core.usage_fetcher import ...`) and correctly target the module object that runs during test execution.
**Original issue:** Tests patch `core.usage_fetcher.httpx` rather than `claude_monitor.core.usage_fetcher.httpx`, making mocks potentially ineffective when running against the installed package.

---

_Fixed: 2026-05-19_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
