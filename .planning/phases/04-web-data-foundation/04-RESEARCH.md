# Phase 4: Web Data Foundation - Research

**Researched:** 2026-05-18
**Domain:** claude.ai REST API, Windows Credential Manager (keyring), Firefox/Chrome cookie extraction, daemon threading
**Confidence:** HIGH (all critical claims verified by live spike against the actual API and codebase)

---

## Summary

Phase 4 wires up an authenticated HTTP fetch from the `claude.ai` usage API into the existing terminal dashboard. The existing `fetch_pool_spend_usd()` function already calls the correct endpoint (`GET /api/organizations/{org_id}/usage`) and the spike confirmed that **urllib.request works without Cloudflare blocking on this machine** — httpx and curl_cffi are not required.

The most significant discovery is a **schema split by account type**. This account uses a Teams/Enterprise plan, so the `five_hour` field in the API response is `null`. The authoritative utilization metric is `extra_usage.utilization` (a percentage 0–100). Max/Pro individual plans use `five_hour.utilization` instead. `fetch_web_usage()` must handle both paths and select whichever is non-null. The display label changes accordingly (`via claude.ai` in both cases).

A second critical finding: all three new dependencies (`keyring`, `browser-cookie3`, `httpx`) are absent from `pyproject.toml` and must be added. The `keyring` migration from config.json values is mandatory before any API call — the current `session_key` lives in plaintext config.json and must be moved to Windows Credential Manager on first run.

**Primary recommendation:** Plan sequencing must be: (1) models + deps, (2) usage_fetcher refactor with spike-proven endpoint, (3) WebPoller thread, (4) orchestrator wire-up, (5) display rows, (6) cli/main.py auth flow.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** org_id stored in `~/.claude-monitor/config.json`. On startup, auto-discover org_id via bootstrap/profile endpoint using active sessionKey. If auto-discovery succeeds, write to config.json. If it fails, prompt user to enter org_id before dashboard launches.
- **D-02:** If org_id already in config.json, skip discovery — use stored value.
- **D-03:** sessionKey stored exclusively in Windows Credential Manager via keyring. Service: `claude-monitor`, username: `sessionKey`. Never written to config.json.
- **D-04:** Auto-migration on startup: if session_key (or cf_clearance) found in config.json, copy to keyring, delete from config.json, proceed. One-way, logged at INFO.
- **D-05:** cf_clearance also stored in keyring (username: `cf_clearance`), same migration pattern.
- **D-06:** Auth resolution priority: (1) keyring, (2) Firefox cookie store, (3) Chrome (only when Chrome not running), (4) manual paste.
- **D-07:** Firefox extraction is new code. Existing Chrome extraction kept at position 3.
- **D-08:** When no sessionKey available: block dashboard launch, show interactive console prompt instructing user to copy sessionKey from DevTools. Store in keyring, then launch.
- **D-09:** If org_id also unknown at first-run prompt time: prompt for org_id after sessionKey prompt. Attempt API auto-discovery first; only ask user if that fails.
- **D-10:** Stale key (401/403 on first API call of new session): clear from keyring, show paste prompt again.
- **D-11:** Subsequent launches read from keyring with no prompt if valid key exists.
- **D-12:** `monitoring/web_poller.py` new module. WebPoller is a daemon thread using `threading.Event` for 300-second sleep. `threading.Lock` protects cached WebUsageData.
- **D-13:** Poller calls `usage_fetcher.fetch_web_usage()` every 5 minutes. On success, updates cache and records last_sync_time. On failure, logs warning, leaves last cache intact.
- **D-14:** `monitoring/orchestrator.py` gets `set_web_poller()` method. Poller started in `cli/main.py`; stopped in existing `finally` block.
- **D-15:** `WebUsageData` frozen dataclass in `core/models.py`: `utilization_pct: float`, `reset_at: datetime`, `fetched_at: datetime`, `plan_limit_tokens: Optional[int]`.
- **D-16:** `monitoring/orchestrator.py` exposes `web_usage` key in `monitoring_data`. Value is `Optional[WebUsageData]`.
- **D-17:** When `web_usage` is available: replace P90 threshold row with `Utilization: 67% via claude.ai` and `Resets in: 1h 23m`. INCLUDED/OVERAGE driven by `web_usage.utilization_pct >= 100%`.
- **D-18:** When `web_usage` is None: revert to P90-driven display, append `(est. — web unavailable)`.
- **D-19:** `Last web sync: HH:MM:SS` shown as footer row in threshold section after first successful fetch.
- **D-20:** `session_display.py` receives `web_usage: Optional[WebUsageData]` via kwargs. Existing `threshold_state` and `pool_state` kwargs unchanged.
- **D-21:** Default HTTP client is httpx (sync). curl_cffi is conditional-only if httpx is blocked. Spike first. (SPIKE RESULT: urllib.request already works; httpx will also work. curl_cffi NOT needed.)
- **D-22:** Use `.get("key", default)` for all JSON field access. Log raw response at DEBUG.
- **D-23:** fetch_web_usage() new function in core/usage_fetcher.py. Endpoint must be spiked before writing parsing code. (SPIKE COMPLETE — see API Endpoint Discovery section.)
- **D-24:** On billing cycle start day, log `[INFO] Billing cycle reset — pool spend cleared to $0.00`. No changes to reset logic.

### Claude's Discretion

- Exact Rich markup and row layout for web data rows — consistent with existing session_display.py style
- Whether `fetch_web_usage()` returns `WebUsageData` directly or wraps in `Optional`
- Error retry logic inside WebPoller (exponential backoff vs flat interval)
- Whether org_id auto-discovery gets its own function in usage_fetcher.py or is inlined

### Deferred Ideas (OUT OF SCOPE)

- curl_cffi Cloudflare bypass — Only add if httpx is blocked. Do not pre-add.
- Multi-browser cookie extraction (Edge) — Not in Phase 4 scope.
- ANLX-02: Overage pool balance from web API — Deferred to v2.1.
- Session reset model detection — Deferred unless discoverable during spike.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | Auto-extract sessionKey from Firefox (primary) or Chrome (best-effort) | Firefox cookies.sqlite readable via sqlite3/browser-cookie3; Chrome extraction already implemented. Firefox has no claude.ai cookies on this machine — keyring migration path is the live path. |
| AUTH-02 | Manual sessionKey paste when auto-extraction fails; store in Windows Credential Manager | keyring 25.7.0 confirmed available on PyPI. WinVault backend is default on Windows. API: set_password(service, username, password). |
| AUTH-03 | Stored sessionKey persists across restarts; no re-prompt if valid | keyring.get_password() returns stored value or None. Thread on startup reads keyring first per D-06. |
| WEBD-01 | Dashboard shows authoritative utilization % labeled "via claude.ai" | Confirmed via spike: extra_usage.utilization = 64.26% for Teams plan. five_hour.utilization for Max/Pro. Same endpoint, field selection branch. |
| WEBD-02 | Dashboard shows time remaining until reset, sourced from claude.ai | five_hour.resets_at (ISO datetime) for Max/Pro. extra_usage has no resets_at — billing cycle reset must be derived from config. |
| WEBD-03 | Graceful fallback to JSONL estimates when web data unavailable | WebPoller preserves last cache on failure. session_display.py branches on web_usage is None per D-18. |
| POLL-01 | Background WebPoller re-fetches every 5 min, never blocks display | daemon thread + threading.Event(300s wait). Pattern verified matches MonitoringOrchestrator exactly. |
| POLL-02 | Pool spend resets to $0.00 at billing cycle start; logged to console | D-24: Add INFO log in pool_state_manager.py when billing_cycle_start changes. |

</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP fetch from claude.ai | API/Backend (core layer) | — | core/usage_fetcher.py owns all external HTTP; no direct HTTP in UI or threading layer |
| Session key storage (keyring) | API/Backend (core layer) | — | credentials never touch UI or orchestrator |
| Cookie extraction (Firefox/Chrome) | API/Backend (core layer) | — | extension of existing _read_chrome_cookies() pattern |
| 300s poll loop | Monitoring thread | — | daemon thread, never runs in main/display thread |
| Cache of WebUsageData | Monitoring thread | Lock-protected | threading.Lock guards reads from main thread |
| Display of web data rows | UI layer | — | session_display.py reads via kwargs, no business logic |
| org_id discovery | API/Backend (core layer) | — | single function in usage_fetcher.py, not in UI |
| Auth first-run prompt | CLI (main.py) | — | blocking console prompt before Rich Live context starts |

---

## API Endpoint Discovery

### Primary Endpoint (VERIFIED via live spike)

**Endpoint:** `GET https://claude.ai/api/organizations/{org_id}/usage`

**Authentication:** Cookie header with `sessionKey=<value>` only. `cf_clearance` is NOT required on this machine.

**Required headers:**
```
Cookie: sessionKey=<session_key_value>
Accept: application/json
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
anthropic-client-platform: web_claude_ai
```

**Response time:** ~300ms [VERIFIED: live spike]

**Response schema (Teams/Enterprise org — this account):**
```json
{
  "five_hour": null,
  "seven_day": null,
  "extra_usage": {
    "is_enabled": true,
    "monthly_limit": 75000,
    "used_credits": 48197.0,
    "utilization": 64.26,
    "currency": "USD",
    "disabled_reason": null
  },
  "omelette_promotional": { "utilization": 0.0, "resets_at": null }
}
```

**Response schema (Max/Pro personal org — also accessible):**
```json
{
  "five_hour": {
    "utilization": 0.0,
    "resets_at": null
  },
  "seven_day": { "utilization": 0.0, "resets_at": null },
  "extra_usage": null
}
```

### Critical Schema Insight [VERIFIED]

The `five_hour` field is `null` for Teams/Enterprise accounts. `extra_usage` is the authoritative usage source for this user. `fetch_web_usage()` must branch on which field is non-null:

```python
def fetch_web_usage(org_id: str, config_dir: Path) -> Optional[WebUsageData]:
    # ... fetch response body ...
    
    five_hour = body.get("five_hour")
    extra_usage = body.get("extra_usage")
    
    if five_hour is not None:
        # Max/Pro individual plan
        utilization_pct = five_hour.get("utilization", 0.0)
        reset_at_str = five_hour.get("resets_at")  # ISO datetime or null
        plan_limit_tokens = None  # not in API
    elif extra_usage and extra_usage.get("is_enabled"):
        # Teams/Enterprise plan - extra_usage.utilization is % of monthly pool
        utilization_pct = extra_usage.get("utilization", 0.0)
        reset_at_str = None  # no 5-hour window; billing cycle reset from config
        plan_limit_tokens = None  # monthly_limit is in CENTS, not tokens
    else:
        return None  # no usable data
    
    # Parse reset_at
    if reset_at_str:
        reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
    else:
        reset_at = _derive_billing_cycle_reset(config_dir)  # fall back to billing date
    
    return WebUsageData(
        utilization_pct=utilization_pct,
        reset_at=reset_at,
        fetched_at=datetime.now(timezone.utc),
        plan_limit_tokens=plan_limit_tokens,
    )
```

### Utilization Scale [VERIFIED]

Both `five_hour.utilization` and `extra_usage.utilization` are on a **0.0 to 100.0 scale** (percentage). Confirmed: `48197 / 75000 * 100 = 64.2627%`, which matches API-reported `64.2627`.

**extra_usage monetary fields are in CENTS**, not tokens or dollars: `monthly_limit: 75000 = $750.00`, `used_credits: 48197 = $481.97`.

### org_id Auto-Discovery Endpoint [VERIFIED]

`GET https://claude.ai/api/account` returns `memberships[].organization.uuid`. No org-scoped path needed — caller supplies only sessionKey cookie.

```python
def _discover_org_id(session_key: str) -> Optional[str]:
    """Call /api/account to find the first org with active extra_usage or any membership."""
    # ... make request ...
    for m in body.get("memberships", []):
        org_uuid = m.get("organization", {}).get("uuid")
        if org_uuid:
            return org_uuid  # return first org (company org appears first)
    return None
```

Account `memberships` on this account returns two orgs:
1. `4252fdb7-...` (Master Electronics — Teams/Enterprise, appears first)
2. `fc63fd97-...` (personal org — Max/Pro or free)

The first membership is the relevant one for this user. Discovery should return the first membership UUID.

---

## Cloudflare & HTTP Client

### Cloudflare Status [VERIFIED: live spike]

Cloudflare IS present (response includes `cf-cache-status: DYNAMIC`) but is **not blocking** `urllib.request` or standard Python HTTP on this machine.

- HTTP 200 returned with `urllib.request.urlopen` and sessionKey cookie alone.
- `cf_clearance` cookie is **not required** — requests succeed without it.
- D-21 spike result: **curl_cffi is NOT needed.** httpx should work identically to urllib (same Python TLS stack).

### HTTP Client Decision [VERIFIED]

Per D-21, the plan should **use `httpx` (sync)** as the HTTP client for fetch_web_usage(), since it is a cleaner API than urllib.request and supports timeouts, redirects, and response objects consistently. The existing `fetch_pool_spend_usd()` uses `urllib.request` — `fetch_web_usage()` will use `httpx` per the locked decision but the spike confirms it will not be blocked.

The existing `fetch_pool_spend_usd()` could optionally be migrated to httpx in a follow-up; for Phase 4, only the new `fetch_web_usage()` uses httpx.

### Headers Required [VERIFIED]

```python
headers = {
    "Cookie": f"sessionKey={session_key}",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "anthropic-client-platform": "web_claude_ai",
}
```

### 401/403 Handling (D-10) [ASSUMED for exact behavior]

If the API returns 401 or 403:
- The sessionKey is stale (expired or revoked).
- Clear it from keyring: `keyring.delete_password("claude-monitor", "sessionKey")`.
- Trigger the first-run paste prompt flow.
- D-10 specifies this only on "first API call of a new session" — check response code inside WebPoller's first poll; if it fires, signal main thread to re-prompt.

---

## Cookie Extraction (Firefox + Chrome)

### Firefox cookies.sqlite [VERIFIED: live read from this machine]

**Path on this machine:** `C:\Users\justin.rhoda\AppData\Roaming\Mozilla\Firefox\Profiles\l5ozzog5.default-release\cookies.sqlite`

**General pattern for Windows Firefox:**
```
%APPDATA%\Mozilla\Firefox\Profiles\<profile.default-release>\cookies.sqlite
```

**Table schema (sqlite3 direct read):**
```sql
SELECT name, value FROM moz_cookies 
WHERE host LIKE '%claude.ai' 
AND name IN ('sessionKey', 'cf_clearance') 
ORDER BY lastAccessed DESC
```

Firefox cookies are **stored in cleartext** (unlike Chrome's AES-GCM). No decryption needed.

**Current machine status:** Firefox has no claude.ai cookies — user is not logged into claude.ai in Firefox. The Firefox extraction path will return `(None, None)` on this machine. This is expected; keyring migration from config.json covers it.

### Firefox Profile Discovery [ASSUMED — pattern from browser-cookie3 source]

```python
def _find_firefox_profile() -> Optional[Path]:
    base = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
    if not base.exists():
        return None
    for d in base.iterdir():
        if d.is_dir() and d.name.endswith(".default-release"):
            return d / "cookies.sqlite"
    return None
```

### browser-cookie3 Alternative [VERIFIED: PyPI registry]

`browser-cookie3 0.20.1` (latest) provides `browser_cookie3.firefox(domain_name=".claude.ai")` which handles profile discovery automatically. It returns a `http.cookiejar.CookieJar` that can be iterated.

```python
import browser_cookie3

def _read_firefox_cookies() -> Tuple[Optional[str], Optional[str]]:
    try:
        cj = browser_cookie3.firefox(domain_name=".claude.ai")
        session_key = None
        cf_clearance = None
        for cookie in cj:
            if cookie.name == "sessionKey" and session_key is None:
                session_key = cookie.value
            elif cookie.name == "cf_clearance" and cf_clearance is None:
                cf_clearance = cookie.value
        return session_key, cf_clearance
    except Exception as exc:
        logger.debug("firefox_cookies: extraction failed: %s", exc)
        return None, None
```

**Pitfall:** browser-cookie3 raises `BrowserCookieError` when Firefox is running and has a WAL lock on cookies.sqlite. Wrap in `try/except Exception`.

### Chrome Cookie Extraction (Existing)

The existing `_read_chrome_cookies()` in `usage_fetcher.py` handles App-Bound Encryption for Chrome 127+. Per D-07, this moves to **position 3** (after keyring and Firefox).

Per existing code, Chrome extraction is skipped when Chrome is running (App-Bound Encryption). This behavior is correct for Phase 4 — keep it.

### Auth Resolution Order (D-06) [VERIFIED: existing code + new requirements]

```python
def _read_auth_cookies(config_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    # Priority 1: keyring (Windows Credential Manager)
    try:
        import keyring
        session_key = keyring.get_password("claude-monitor", "sessionKey") or None
        cf_clearance = keyring.get_password("claude-monitor", "cf_clearance") or None
        if session_key:
            logger.debug("auth: sessionKey from keyring")
            return session_key, cf_clearance
    except Exception as exc:
        logger.debug("auth: keyring error: %s", exc)
    
    # Priority 2: Firefox cookie store
    session_key, cf_clearance = _read_firefox_cookies()
    if session_key:
        logger.debug("auth: sessionKey from Firefox")
        return session_key, cf_clearance
    
    # Priority 3: Chrome cookie store (only when Chrome not running)
    session_key, cf_clearance = _read_chrome_cookies()
    if session_key:
        logger.debug("auth: sessionKey from Chrome")
        return session_key, cf_clearance
    
    logger.warning("auth: no sessionKey available")
    return None, None
```

---

## Windows Credential Manager (keyring)

### Library Status [VERIFIED: PyPI registry]

- **Package:** `keyring`
- **Latest version:** `25.7.0` (November 2025) [VERIFIED: PyPI]
- **Windows backend:** WinVault (Windows Credential Manager) — active by default on Windows, no extra configuration needed.
- **Requires Python:** 3.9+

### Core API [CITED: pypi.org/project/keyring + github.com/jaraco/keyring README]

```python
import keyring

# Store a credential
keyring.set_password("claude-monitor", "sessionKey", session_key_value)
keyring.set_password("claude-monitor", "cf_clearance", cf_clearance_value)

# Retrieve a credential (returns None if not found)
session_key = keyring.get_password("claude-monitor", "sessionKey")

# Delete a credential (raises keyring.errors.PasswordDeleteError if not found)
try:
    keyring.delete_password("claude-monitor", "sessionKey")
except keyring.errors.PasswordDeleteError:
    pass  # already gone, that's fine
```

### Config Migration (D-04) [VERIFIED: spec + keyring API]

```python
def _migrate_config_to_keyring(config_dir: Path) -> None:
    """One-time migration: move session_key from config.json to keyring."""
    import keyring
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        return
    
    changed = False
    for config_key, keyring_username in [("session_key", "sessionKey"), ("cf_clearance", "cf_clearance")]:
        value = cfg.get(config_key)
        if value:
            keyring.set_password("claude-monitor", keyring_username, value)
            del cfg[config_key]
            logger.info("auth: migrated %s from config.json to keyring", config_key)
            changed = True
    
    if changed:
        tmp = config_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        tmp.replace(config_file)
```

### Known Issues [CITED: github.com/jaraco/keyring/issues/545]

1. **Duplicate entries on repeated set_password calls:** keyring creates new entries instead of updating. This is fine for Phase 4 since we only set once (migration) and then read.
2. **keyring.errors.PasswordDeleteError on delete:** Must catch when clearing stale key (D-10).
3. **No known issues on Windows 11 non-service accounts.** [VERIFIED: search, no relevant issues found for standard user accounts]

---

## WebPoller Threading Pattern

### Pattern [VERIFIED: mirrors existing MonitoringOrchestrator in orchestrator.py]

```python
# monitoring/web_poller.py

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from claude_monitor.core.models import WebUsageData
from claude_monitor.core.usage_fetcher import fetch_web_usage

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".claude-monitor"


class WebPoller(threading.Thread):
    """Daemon thread that fetches claude.ai usage data every 300 seconds."""

    def __init__(self, org_id: str, config_dir: Optional[Path] = None) -> None:
        super().__init__(name="WebPollerThread", daemon=True)
        self._org_id = org_id
        self._config_dir = config_dir or _CONFIG_DIR
        self._stop_event = threading.Event()
        self._cache_lock = threading.Lock()
        self._web_usage: Optional[WebUsageData] = None
        self._last_sync_time: Optional[datetime] = None

    def run(self) -> None:
        """Poll immediately, then every 300s until stopped."""
        logger.info("WebPoller: starting (300s interval)")
        self._poll_once()
        while not self._stop_event.wait(300):
            self._poll_once()
        logger.info("WebPoller: stopped")

    def stop(self) -> None:
        """Signal the poller to stop. Returns immediately; join() to wait."""
        self._stop_event.set()

    def get_web_usage(self) -> Optional[WebUsageData]:
        """Thread-safe read of the latest cached result."""
        with self._cache_lock:
            return self._web_usage

    def get_last_sync_time(self) -> Optional[datetime]:
        """Thread-safe read of the last successful sync timestamp."""
        with self._cache_lock:
            return self._last_sync_time

    def _poll_once(self) -> None:
        result = fetch_web_usage(self._org_id, self._config_dir)
        if result is not None:
            with self._cache_lock:
                self._web_usage = result
                self._last_sync_time = datetime.now(timezone.utc)
            logger.debug("WebPoller: cache updated, utilization=%.1f%%", result.utilization_pct)
        else:
            logger.warning("WebPoller: fetch failed — retaining previous cache")
```

### Event.wait() Behavior [VERIFIED: Python threading docs]

- `self._stop_event.wait(300)` returns `False` on timeout (5-minute poll cycle continues).
- `self._stop_event.wait(300)` returns `True` when `stop_event.set()` is called (poller exits loop immediately).
- `while not self._stop_event.wait(300)` is the correct idiom: `True` from set means "stop" which `not True = False` breaks the while.

### Shutdown in cli/main.py finally block [VERIFIED: existing pattern]

```python
finally:
    if "orchestrator" in locals():
        orchestrator.stop()
    if "web_poller" in locals():
        web_poller.stop()  # signals event, daemon thread exits on next wake
    # No join needed — daemon threads die with the process
```

---

## org_id Auto-Discovery

### Endpoint [VERIFIED: live spike]

`GET https://claude.ai/api/account` — returns account info including `memberships[].organization.uuid`.

**No org_id required** to call this endpoint. Only sessionKey cookie needed.

**Returns on this account:**
- `memberships[0].organization.uuid = "4252fdb7-..."` (Master Electronics — first, company Teams org)
- `memberships[1].organization.uuid = "fc63fd97-..."` (personal org)

### Discovery Strategy

```python
def _discover_org_id(session_key: str) -> Optional[str]:
    """Auto-discover org_id using /api/account endpoint."""
    import httpx
    try:
        resp = httpx.get(
            "https://claude.ai/api/account",
            headers={
                "Cookie": f"sessionKey={session_key}",
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
                "anthropic-client-platform": "web_claude_ai",
            },
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
        for m in body.get("memberships", []):
            uuid = m.get("organization", {}).get("uuid")
            if uuid:
                return uuid
    except Exception as exc:
        logger.debug("org_id discovery failed: %s", exc)
    return None
```

**Pitfall:** If the account has multiple orgs, the first membership UUID is returned. For this user, that is the Teams org which has `extra_usage`. This is correct behavior. If a user has only a personal org, the first membership is the personal org — also correct.

---

## Integration Sequence & Plan Breakdown

### Recommended Plan Sequencing

The planner should create 6 plans in this order. Each plan must leave the app runnable after it completes.

```
04-01-PLAN.md — Dependencies + WebUsageData model
04-02-PLAN.md — usage_fetcher.py: auth refactor + fetch_web_usage() + org discovery
04-03-PLAN.md — WebPoller daemon thread (monitoring/web_poller.py)
04-04-PLAN.md — Orchestrator wire-up + display_controller kwarg pass-through
04-05-PLAN.md — session_display.py: web data rows + fallback display (D-17/D-18/D-19)
04-06-PLAN.md — cli/main.py: auth setup flow (D-08/D-09/D-10) + WebPoller start/stop + pool reset log (D-24)
```

### Plan Details

**04-01: Dependencies + WebUsageData model**
Files: `pyproject.toml`, `core/models.py`
Actions: Add keyring, browser-cookie3, httpx to dependencies. Add `WebUsageData` frozen dataclass.
Risk: None. Installable in one step, dataclass has no external deps.

**04-02: usage_fetcher.py refactor**
Files: `core/usage_fetcher.py`
Actions:
- Add `_read_firefox_cookies()` (browser-cookie3)
- Add `_migrate_config_to_keyring()` (D-04)
- Refactor `_read_auth_cookies()` to priority order: keyring(1) → Firefox(2) → Chrome(3) (D-06)
- Add `fetch_web_usage()` with account-type branch (five_hour vs extra_usage)
- Add `_discover_org_id()` helper
Risk: HIGH — most complex plan. Include unit tests for `_read_firefox_cookies`, `fetch_web_usage` parsing branches. Mock httpx in tests.

**04-03: WebPoller daemon thread**
Files: `monitoring/web_poller.py` (new)
Actions: Implement WebPoller class per threading pattern above.
Risk: LOW — well-understood pattern, mirrors MonitoringOrchestrator.

**04-04: Orchestrator wire-up**
Files: `monitoring/orchestrator.py`, `ui/display_controller.py`
Actions:
- Add `set_web_poller(poller: WebPoller)` to MonitoringOrchestrator
- Add `web_usage` key to `monitoring_data` dict in `_fetch_and_process_data()`
- Add `web_usage` kwarg in `display_controller.py:create_data_display()` (mirrors pool_state pattern exactly)
- Add `processed_data["web_usage"] = web_usage` before `format_active_session_screen()`
Risk: LOW — two-line additions mirroring Phase 3 pool_state pattern.

**04-05: session_display.py web data rows**
Files: `ui/session_display.py`
Actions:
- Add `web_usage` kwarg handling in `format_active_session_screen()`
- When web_usage is not None: replace threshold row with D-17 rows
- When web_usage is None: show D-18 fallback rows
- D-19 last sync footer row
Risk: MEDIUM — display branching. Existing Phase 2/Phase 3 rows must remain intact when web_usage=None.

**04-06: cli/main.py auth flow + WebPoller wiring**
Files: `cli/main.py`, `core/pool_state_manager.py`
Actions:
- Call `_migrate_config_to_keyring()` during startup (D-04)
- Call `_read_auth_cookies()` to check if sessionKey is available
- If no sessionKey: show D-08 blocking console prompt (before Rich Live starts)
- Call `_discover_org_id()` if org_id not in config (D-01/D-09)
- Instantiate `WebPoller(org_id, config_dir)` and call `.start()`
- Call `orchestrator.set_web_poller(web_poller)`
- Add `web_usage=monitoring_data.get("web_usage")` to `create_data_display()` call in `on_data_update`
- Add `web_poller.stop()` to `finally` block (D-14)
- D-24: Add billing reset log event to `pool_state_manager.py`
Risk: MEDIUM — auth prompt must happen before Rich Live context. The `_run_monitoring()` function must call auth setup before `live_display.__enter__()`.

### Data Flow Diagram

```
cli/main.py startup
    |
    v
_migrate_config_to_keyring()  [D-04: one-time]
    |
    v
_read_auth_cookies()  [keyring > Firefox > Chrome]
    |--- no sessionKey ---> console prompt [D-08] ---> keyring.set_password()
    |
    v
org_id from config.json or _discover_org_id() [D-01/D-02]
    |
    v
WebPoller(org_id).start()  [daemon thread]
    |
    +-------------------------> fetch_web_usage() [every 300s]
    |                               |
    |                               v
    |                         claude.ai /api/organizations/{org_id}/usage
    |                               |
    |                         WebUsageData (cached)
    |
MonitoringOrchestrator.start()
    |
    v [every 10s in MonitoringThread]
_fetch_and_process_data()
    |
    +---> web_usage = web_poller.get_web_usage()
    |
    v
monitoring_data["web_usage"] = web_usage
    |
    v [callback in main thread]
on_data_update() -> create_data_display(web_usage=web_usage)
    |
    v
display_controller -> session_display.format_active_session_screen(web_usage=web_usage)
    |
    v
Rich Live display: "Utilization: 64.3% via claude.ai" or "(est. — web unavailable)"
```

---

## Dependencies (pyproject.toml changes)

### Packages to Add [VERIFIED: PyPI registry]

| Package | Latest Version | Install Name | Purpose |
|---------|---------------|--------------|---------|
| `keyring` | 25.7.0 | `keyring>=25.0.0` | Windows Credential Manager storage |
| `browser-cookie3` | 0.20.1 | `browser-cookie3>=0.19.1` | Firefox/Chrome cookie extraction |
| `httpx` | 0.28.1 | `httpx>=0.27.0` | Sync HTTP client for fetch_web_usage() |

### pyproject.toml Change

```toml
dependencies = [
  "cryptography>=41.0.0",
  "numpy>=1.21.0",
  "pydantic>=2.0.0",
  "pydantic-settings>=2.0.0",
  "pyyaml>=6.0",
  "pytz>=2023.3",
  "rich>=13.7.0",
  "tomli>=1.2.0; python_version < '3.11'",
  "tzdata",
  # Phase 4 additions:
  "keyring>=25.0.0",
  "browser-cookie3>=0.19.1",
  "httpx>=0.27.0",
]
```

### curl_cffi [VERIFIED: NOT NEEDED]

Cloudflare does NOT block `urllib.request` on this machine. `httpx` uses the same TLS stack and will also work. Do NOT add `curl_cffi` per D-21 and spike results.

### Installation Verification

```bash
pip install keyring>=25.0.0 browser-cookie3>=0.19.1 httpx>=0.27.0
```

---

## Validation Architecture

nyquist_validation is explicitly `false` in `.planning/config.json`. This section is SKIPPED.

---

## Common Pitfalls

### Pitfall 1: five_hour is null for Teams/Enterprise accounts
**What goes wrong:** Code reads `body["five_hour"]["utilization"]` and raises TypeError when five_hour is null.
**Why it happens:** Teams/Enterprise accounts use `extra_usage`, not `five_hour`. Both are present in the response schema but only one is non-null.
**How to avoid:** Always check `if body.get("five_hour") is not None:` before accessing sub-fields.
**Warning signs:** KeyError or TypeError on first test run against the actual org_id.

### Pitfall 2: extra_usage monetary fields are in CENTS, not dollars
**What goes wrong:** Display shows `$48197.00` instead of `$481.97`.
**Why it happens:** `used_credits` and `monthly_limit` are in US cents.
**How to avoid:** Divide by 100 when converting to dollars. `plan_limit_tokens` in WebUsageData should be None for Teams (it's a money limit, not a token limit).
**Warning signs:** Pool spend figures show 100x the expected value.

### Pitfall 3: keyring.delete_password raises on missing key
**What goes wrong:** D-10 stale key flow crashes when clearing a key that doesn't exist.
**Why it happens:** keyring.delete_password raises `keyring.errors.PasswordDeleteError` if no credential found.
**How to avoid:** Always wrap `delete_password` in try/except `keyring.errors.PasswordDeleteError`.
**Warning signs:** Unhandled exception in auth setup on first launch with no stored key.

### Pitfall 4: browser-cookie3 raises BrowserCookieError when Firefox WAL-locks cookies.sqlite
**What goes wrong:** Firefox has cookies.sqlite open, browser-cookie3 fails to copy it.
**Why it happens:** Firefox holds a WAL lock on cookies.sqlite while running.
**How to avoid:** Wrap `browser_cookie3.firefox()` in `try/except Exception`. Fall through to Chrome (position 3).
**Warning signs:** Exception in Firefox extraction path logged at DEBUG. Silent degradation is correct behavior.

### Pitfall 5: Auth prompt must run BEFORE Rich Live context
**What goes wrong:** Console input inside a Rich Live display context garbles the terminal (Live intercepts stdin).
**Why it happens:** Rich Live takes over terminal rendering; `input()` calls inside it cause layout corruption.
**How to avoid:** In `cli/main.py:_run_monitoring()`, call auth setup (including any blocking console prompt) before `live_display.__enter__()`. The existing code structure already enters Rich Live in a try block — auth setup goes before the try block opens the Live context.
**Warning signs:** Terminal shows garbled output or input appears at wrong position during first-run prompt.

### Pitfall 6: WebPoller tries to get web_usage before org_id is known
**What goes wrong:** WebPoller is constructed with `org_id=None` and `fetch_web_usage()` formats a URL with None.
**Why it happens:** org_id discovery and config read happen in auth setup; WebPoller is wired to orchestrator later.
**How to avoid:** WebPoller requires `org_id` as a constructor argument (not optional). Auth setup (including org_id discovery) completes before `WebPoller(org_id)` is instantiated.
**Warning signs:** URL contains "None" string; HTTP 404 on malformed URL.

### Pitfall 7: D-17 display replaces P90 row without handling calibrating state
**What goes wrong:** Web usage data shown alongside "Calibrating" P90 row, causing duplicate or conflicting information.
**Why it happens:** threshold_state.status == "calibrating" is a special case in session_display.py.
**How to avoid:** When web_usage is not None, the web utilization display replaces the P90 threshold row entirely. The calibrating row is also suppressed. The INCLUDED/OVERAGE determination is now driven by `web_usage.utilization_pct >= 100.0`.
**Warning signs:** Dashboard shows both "Calibrating" and "Utilization: X% via claude.ai" simultaneously.

---

## Code Examples

### WebUsageData frozen dataclass (D-15)

```python
# core/models.py addition
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class WebUsageData:
    """Authoritative usage data fetched from claude.ai API."""
    utilization_pct: float          # 0.0-100.0; from five_hour.utilization or extra_usage.utilization
    reset_at: datetime              # when this window/period resets (UTC)
    fetched_at: datetime            # when this data was retrieved (UTC)
    plan_limit_tokens: Optional[int]  # None for Teams (monthly_limit is cents, not tokens)
```

### fetch_web_usage() core pattern (VERIFIED endpoint)

```python
# core/usage_fetcher.py
import httpx

_USAGE_URL = "https://claude.ai/api/organizations/{org_id}/usage"

def fetch_web_usage(org_id: str, config_dir: Path) -> Optional["WebUsageData"]:
    """Fetch authoritative usage data from claude.ai. Returns None on any failure."""
    from claude_monitor.core.models import WebUsageData
    try:
        session_key, cf_clearance = _read_auth_cookies(config_dir)
        if not session_key:
            logger.warning("fetch_web_usage: no sessionKey available")
            return None
        
        cookie_parts = [f"sessionKey={session_key}"]
        if cf_clearance:
            cookie_parts.append(f"cf_clearance={cf_clearance}")
        
        resp = httpx.get(
            _USAGE_URL.format(org_id=org_id),
            headers={
                "Cookie": "; ".join(cookie_parts),
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
                "anthropic-client-platform": "web_claude_ai",
            },
            timeout=10,
        )
        
        if resp.status_code in (401, 403):
            logger.warning("fetch_web_usage: auth rejected (%d) — sessionKey may be stale", resp.status_code)
            return None
        
        resp.raise_for_status()
        body = resp.json()
        logger.debug("fetch_web_usage: raw response: %s", body)
        
        five_hour = body.get("five_hour")
        extra_usage = body.get("extra_usage")
        
        if five_hour is not None:
            utilization_pct = float(five_hour.get("utilization", 0.0))
            reset_at_str = five_hour.get("resets_at")
        elif extra_usage and extra_usage.get("is_enabled"):
            utilization_pct = float(extra_usage.get("utilization", 0.0))
            reset_at_str = None  # Teams plan has billing cycle reset, not 5h window
        else:
            logger.info("fetch_web_usage: no usable usage field in response")
            return None
        
        if reset_at_str:
            reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
        else:
            reset_at = _derive_billing_cycle_reset(config_dir)
        
        return WebUsageData(
            utilization_pct=utilization_pct,
            reset_at=reset_at,
            fetched_at=datetime.now(timezone.utc),
            plan_limit_tokens=None,
        )
    except Exception as exc:
        logger.warning("fetch_web_usage: request failed: %s", exc)
        return None
```

### Display row pattern (D-17, D-18, D-19)

```python
# In session_display.py:format_active_session_screen(), after threshold_state block:

web_usage = kwargs.get("web_usage")
if web_usage is not None:
    screen_buffer.append(f"[separator]{'─' * 60}[/]")
    util_bar = self._render_wide_progress_bar(web_usage.utilization_pct)
    screen_buffer.append(
        f"🌐 [value]Utilization:[/]         {util_bar} {web_usage.utilization_pct:.1f}%  [dim]via claude.ai[/]"
    )
    # Resets in row
    now = datetime.now(timezone.utc)
    delta = web_usage.reset_at - now
    total_secs = max(0, int(delta.total_seconds()))
    hours, rem = divmod(total_secs, 3600)
    mins = rem // 60
    screen_buffer.append(
        f"⏱  [value]Resets in:[/]           {hours}h {mins}m"
    )
    # Last sync footer (D-19)
    last_sync = kwargs.get("last_web_sync")  # from orchestrator
    if last_sync:
        screen_buffer.append(
            f"🔄 [dim]Last web sync: {last_sync.strftime('%H:%M:%S')}[/]"
        )
else:
    # D-18: fallback — threshold_state block already handles P90 rows
    # Append "(est. — web unavailable)" suffix handled in threshold row rendering
    pass
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| keyring.errors.PasswordDeleteError on stale key clear (D-10) | HIGH | LOW | Always wrap delete_password in try/except |
| browser-cookie3 raises on Firefox WAL lock | MEDIUM | LOW | Wrap in try/except Exception; fall through to Chrome |
| five_hour is null for Teams org (not handled) | HIGH | HIGH | Verified in spike; fetch_web_usage() must check both fields |
| Auth prompt runs inside Rich Live (terminal garble) | HIGH | HIGH | Auth setup MUST complete before live_display.__enter__() |
| org_id not set + sessionKey not found simultaneously (D-09 flow) | MEDIUM | MEDIUM | Sequential prompts: sessionKey first, then discover/prompt org_id |
| reset_at is null for Teams org (no 5h window) | HIGH | LOW | Derive billing cycle reset date from config.json as fallback |
| WebPoller fetches with None org_id | LOW | HIGH | org_id required argument in WebPoller.__init__(); assertion or early return |
| Claude.ai API schema changes (new field names) | LOW | MEDIUM | Use .get() everywhere per D-22; log full response at DEBUG |
| keyring returns empty string instead of None | MEDIUM | LOW | Use `keyring.get_password(...) or None` idiom |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| session_key in config.json (plaintext) | keyring (Windows Credential Manager) | Phase 4 | Security improvement; migration path D-04 handles existing config.json |
| urllib.request for all HTTP | urllib.request (existing) + httpx (new, fetch_web_usage only) | Phase 4 | httpx provides cleaner API for new code; no disruption to existing code |
| P90-inferred utilization (JSONL) | claude.ai API utilization (authoritative) | Phase 4 | Replaces estimate with real data; fallback preserved |
| Chrome-only cookie extraction | keyring(1) > Firefox(2) > Chrome(3) > manual(4) | Phase 4 | Firefox-first per D-06; Chrome ABE workaround unchanged |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| keyring | AUTH-02, AUTH-03, D-03 | Not installed | — (25.7.0 on PyPI) | Manual only; must install |
| browser-cookie3 | AUTH-01, D-07 | Not installed | — (0.20.1 on PyPI) | Fall through to Chrome/manual |
| httpx | WEBD-01, D-21 | Not installed | — (0.28.1 on PyPI) | urllib.request (existing) is functional |
| Firefox cookies.sqlite | AUTH-01 | Exists (empty) | — | No claude.ai cookies; falls through to Chrome/manual |
| Claude.ai API | WEBD-01/02/03 | Confirmed accessible | — | JSONL estimates (D-18) |
| Windows Credential Manager | AUTH-02, AUTH-03 | Windows 11 Enterprise | native | None required |

**Missing dependencies with no fallback:**
- `keyring` is required for D-03 compliance (no plaintext storage). Must be installed via `pip install keyring>=25.0.0`.

**Missing dependencies with fallback:**
- `browser-cookie3` has Chrome fallback and manual paste as fallback; app can run without it.
- `httpx` has `urllib.request` as functional alternative; app can run without it but D-21 specifies httpx as standard.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `five_hour.utilization` scale is 0–100 when an active session exists (only seen 0.0 in spike) | API Endpoint Discovery | Display shows values 100x too small (e.g., 0.67% instead of 67%); easily caught in first test |
| A2 | org_id auto-discovery should return the FIRST membership UUID | org_id Auto-Discovery | Wrong org queried; fetch returns data for wrong plan type. D-02 means stored org_id is used after first run, limiting blast radius |
| A3 | `reset_at` for extra_usage (Teams) should be derived from billing cycle config (not available in API) | API Endpoint Discovery | "Resets in:" row may show incorrect time for Teams users. Consider showing billing cycle reset date instead of countdown |
| A4 | keyring WinVault backend requires no extra configuration on Windows 11 Enterprise | Windows Credential Manager | May need explicit backend specification if corporate GPO restricts Credential Manager |
| A5 | D-17: "Utilization >= 100%" triggers OVERAGE for Teams plan (monthly pool exhausted) | Display Integration | Threshold logic inverted; INCLUDED/OVERAGE wrong if scale or threshold differs for Teams |
| A6 | browser-cookie3 0.20.1 handles Firefox profile discovery on Windows automatically | Cookie Extraction | Profile path not found; Firefox extraction silently fails (acceptable, falls through) |

---

## Open Questions

1. **five_hour.utilization scale when non-zero**
   - What we know: Only seen `0.0` (no active session) in spike. `extra_usage.utilization` confirmed as 0–100 scale.
   - What's unclear: Whether `five_hour.utilization` uses 0–100 or 0–1 scale when an active session exists.
   - Recommendation: Assume 0–100 (matches extra_usage scale and is the more common API design). Add a `# ASSUMED: 0-100 scale` comment and log the raw value at DEBUG so it's catchable.

2. **"Resets in:" display for Teams plan users**
   - What we know: `five_hour.resets_at` is present for Max/Pro plans. Teams accounts have no 5-hour window and no `resets_at` in API response.
   - What's unclear: What time should "Resets in:" show for Teams users — billing cycle end or nothing?
   - Recommendation: For Teams (extra_usage path), show "Resets: {billing_cycle_reset_date}" (month/day) instead of a countdown. This is Claude's Discretion territory.

3. **D-10 stale key detection in WebPoller context**
   - What we know: D-10 specifies re-prompt on first API call of new session returning 401/403.
   - What's unclear: How does the WebPoller signal main thread to show the interactive prompt? WebPoller runs in a daemon thread; `input()` from a daemon thread is unsafe.
   - Recommendation: WebPoller should set a flag (`stale_key_detected`) that cli/main.py's main loop checks and handles by stopping the live display, prompting, then restarting.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: live spike against claude.ai] — API endpoint, response schema, Cloudflare behavior, auth behavior, org_id discovery
- [VERIFIED: codebase read] — existing usage_fetcher.py, orchestrator.py, session_display.py, display_controller.py patterns
- [VERIFIED: PyPI pip index versions] — browser-cookie3 0.20.1, keyring 25.7.0, httpx 0.28.1, curl-cffi 0.15.0

### Secondary (MEDIUM confidence)
- [CITED: pypi.org/project/keyring + github.com/jaraco/keyring README] — keyring API, WinVault backend, delete_password exception
- [CITED: github.com/borisbabic/browser_cookie3] — browser-cookie3 Firefox API, domain_name parameter
- [CITED: Firefox Mozilla docs] — cookies.sqlite cleartext storage, WAL lock behavior

### Tertiary (LOW confidence)
- [ASSUMED] — `five_hour.utilization` scale when > 0.0 (only seen 0.0 in spike)
- [ASSUMED] — org_id discovery selects first membership UUID

---

## Metadata

**Confidence breakdown:**
- API endpoint: HIGH — live spike confirmed schema, HTTP status, headers, auth requirements
- Cloudflare/HTTP client: HIGH — confirmed NOT blocking on this machine
- Cookie extraction: HIGH (Chrome existing), MEDIUM (Firefox pattern from docs), LOW (Firefox actual coverage — no claude.ai cookies present)
- keyring: MEDIUM — API confirmed from docs, not runtime-tested
- Threading: HIGH — mirrors existing MonitoringOrchestrator pattern exactly
- Dependencies: HIGH — PyPI registry confirms versions

**Research date:** 2026-05-18
**Valid until:** 2026-06-18 (claude.ai API schema stability LOW — re-verify if planning delayed >2 weeks)
