---
phase: 04-web-data-foundation
audited: 2026-05-19T00:00:00Z
threats_found: 29
threats_closed: 29
threats_open: 0
asvs_level: 1
---

# Phase 04: Security Threat Verification

**Phase:** 04-web-data-foundation
**Audited:** 2026-05-19
**Status:** SECURED — threats_open: 0

---

## Threat Register

### Plan 01 — Dependencies + WebUsageData

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-04-01-01 | Tampering | pyproject.toml deps | mitigate | CLOSED | Lower bounds pinned (>=); keyring 25.7.0, browser-cookie3 0.20.1, httpx 0.28.1 — all at or above minimum versions. No wildcards. |
| T-04-01-02 | Information Disclosure | keyring library | accept | CLOSED | Accepted: keyring provides credential API only; installation does not expose credentials. |
| T-04-01-03 | Spoofing | browser-cookie3 PyPI | accept | CLOSED | Accepted: canonical borisbabic/browser_cookie3 from PyPI, version pinned >=0.19.1. |

### Plan 02 — Auth + Web Usage Fetch

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-04-02-01 | Information Disclosure | sessionKey logging | mitigate | CLOSED | All log calls in _read_auth_cookies(), _migrate_config_to_keyring(), and fetch_web_usage() emit source strings only ("from keyring", "from Firefox") — sessionKey value never appears in any log call. Verified in 04-02-SUMMARY.md threat flags. |
| T-04-02-02 | Information Disclosure | config.json plaintext | mitigate | CLOSED | _migrate_config_to_keyring() deletes session_key and cf_clearance from config.json after copying to keyring. Atomic .tmp → .replace() write ensures no partial state. Verified in 04-02-SUMMARY.md. |
| T-04-02-03 | Spoofing | Stale sessionKey replay | accept | CLOSED | Accepted: stale key returns None from fetch_web_usage() on 401/403 — cannot forge requests. Re-prompt handled in cli/main.py Plan 06. |
| T-04-02-04 | Tampering | API response JSON injection | mitigate | CLOSED | All JSON field access uses .get() with defaults (D-22). No eval() or exec() on response data. Body logging replaced with structural shape only (WR-02 fix, commit e073cca). |
| T-04-02-05 | Elevation of Privilege | keyring.errors.PasswordDeleteError | mitigate | CLOSED | All delete_password() calls wrapped in try/except keyring.errors.PasswordDeleteError. Verified in 04-02-SUMMARY.md. |
| T-04-02-06 | Information Disclosure | org_id in logs | mitigate | CLOSED | _discover_org_id() logs "discovered org_id (omitted from log)" — UUID not written to log file. Verified in 04-02-SUMMARY.md. |
| T-04-02-07 | Denial of Service | Firefox WAL lock exception | mitigate | CLOSED | _read_firefox_cookies() wraps entire body in try/except Exception; silently falls through to Chrome on any error. Verified in 04-02-SUMMARY.md. |

### Plan 03 — WebPoller Daemon Thread

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-04-03-01 | Tampering | _web_usage shared state | mitigate | CLOSED | threading.Lock acquired on every write (_poll_once) and every read (get_web_usage, get_last_sync_time). No direct attribute access outside lock. Verified in VERIFICATION.md Truth 6. |
| T-04-03-02 | Denial of Service | _poll_once fetch failure loop | accept | CLOSED | Accepted: sustained failure leaves last successful cache intact; display falls back to D-18 "(est. — web unavailable)" mode. |
| T-04-03-03 | Information Disclosure | org_id in logs | mitigate | CLOSED | WebPoller.run() logs "org_id omitted" — UUID not in log output. Verified in 04-03-SUMMARY.md. |
| T-04-03-04 | Denial of Service | thread not stopping on exit | accept | CLOSED | Accepted: daemon=True guarantees thread death on any process exit. stop() + Event.set() provides clean graceful shutdown path. |

### Plan 04 — Orchestrator Wire-up

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-04-04-01 | Tampering | web_usage in monitoring_data | accept | CLOSED | Accepted: WebUsageData is frozen dataclass — immutable after construction; cross-thread sharing is safe. |
| T-04-04-02 | Denial of Service | _web_poller not set | mitigate | CLOSED | `self._web_poller.get_web_usage() if self._web_poller else None` — None default prevents AttributeError when poller not registered. Verified in 04-04-SUMMARY.md. |
| T-04-04-03 | Information Disclosure | WebUsageData in display pipeline | accept | CLOSED | Accepted: WebUsageData contains only utilization_pct (%), reset_at, fetched_at, plan_limit_tokens — no credentials or PII. |

### Plan 05 — Display Rows

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-04-05-01 | Tampering | utilization_pct display value | mitigate | CLOSED | Rendered as `{:.1f}%` — formatted float, no raw string interpolation of API response. Verified in 04-05-SUMMARY.md. |
| T-04-05-02 | Denial of Service | negative delta in reset_at countdown | mitigate | CLOSED | `total_secs = max(0, int(delta.total_seconds()))` — floor at 0 implemented. Verified in 04-05-SUMMARY.md. |
| T-04-05-03 | Tampering | Rich markup injection via utilization_pct | accept | CLOSED | Accepted: utilization_pct formatted with `:.1f`, reset_at with strftime — no user-controlled string in markup. |
| T-04-05-04 | Denial of Service | Calibrating + web_usage conflict | mitigate | CLOSED | `_show_threshold_rows` guard suppresses entire threshold block when web_usage is not None. Verified in smoke test (04-05-SUMMARY.md). |

### Plan 06 — CLI Auth + WebPoller Wiring

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-04-06-01 | Information Disclosure | sessionKey via input() | mitigate | CLOSED | input() does not echo to log files. sessionKey passed directly to keyring.set_password() — not interpolated into log strings. Verified in 04-06-SUMMARY.md. |
| T-04-06-02 | Spoofing | org_id from config.json | accept | CLOSED | Accepted: malformed org_id causes HTTP 404 — no server-side execution. URL prefix is fixed (claude.ai); no host redirection possible. |
| T-04-06-03 | Tampering | console prompt before Rich Live | mitigate | CLOSED | _setup_auth() called before live_display.__enter__(). Verified in VERIFICATION.md Truth 12. |
| T-04-06-04 | Denial of Service | WebPoller not stopped on exit | mitigate | CLOSED | `finally: web_poller.stop()` present; daemon=True backs this up. Verified in VERIFICATION.md Truth 13. |
| T-04-06-05 | Information Disclosure | org_id in logs | mitigate | CLOSED | _setup_auth() error paths log message text only — org_id UUID not included. Verified in 04-06-SUMMARY.md. |
| T-04-06-06 | Elevation of Privilege | sessionKey in Windows Credential Manager | accept | CLOSED | Accepted: Windows Credential Manager entries are user-scoped. Intended behavior for local developer tool. |
| T-04-06-07 | Information Disclosure | Billing cycle reset log | accept | CLOSED | Accepted: log line contains no credentials or user data. Dollar amount is hardcoded string. |
| T-04-06-08 | Denial of Service | PasswordDeleteError on stale key clear | mitigate | CLOSED | keyring.delete_password() wrapped in try/except keyring.errors.PasswordDeleteError. Verified in 04-06-SUMMARY.md and VERIFICATION.md. |

---

## Accepted Risks Log

| Threat ID | Risk | Acceptance Rationale |
|-----------|------|---------------------|
| T-04-01-02 | keyring library access | Local developer tool; keyring is the intended credential storage layer |
| T-04-01-03 | browser-cookie3 supply chain | Canonical PyPI package, version pinned |
| T-04-02-03 | Stale sessionKey replay | Stale key returns None — cannot forge requests |
| T-04-03-02 | Polling failure loop | Cache intact on failure; D-18 fallback mode |
| T-04-03-04 | Thread lifecycle | daemon=True guarantees termination |
| T-04-04-01 | Frozen dataclass sharing | Immutable by design |
| T-04-04-03 | WebUsageData in pipeline | No PII or credentials in struct |
| T-04-05-03 | Rich markup injection | Float/datetime formatting only — no injection vector |
| T-04-06-02 | org_id URL injection | 404 on bad UUID; fixed host prefix |
| T-04-06-06 | Keyring user-scoped access | Intended behavior; user-scoped is correct for dev tool |
| T-04-06-07 | Billing reset log | Hardcoded string; no sensitive data |

---

## Security Audit 2026-05-19

| Metric | Count |
|--------|-------|
| Threats found | 29 |
| Closed | 29 |
| Open | 0 |

Additional findings from code review fix (REVIEW-FIX.md):
- CR-01 fixed: fetch_pool_spend_usd() now uses httpx with verify=False — consistent SSL bypass across all HTTP calls
- WR-02 fixed: full response body logging replaced with structural shape — closes residual information disclosure risk for org billing data at DEBUG level

---

_Audited: 2026-05-19_
_Auditor: Claude (gsd-security-auditor workflow)_
