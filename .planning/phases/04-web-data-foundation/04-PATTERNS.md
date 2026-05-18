# Phase 4: Web Data Foundation - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 8 (new/modified)
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pyproject.toml` | config | — | `pyproject.toml` (self) | exact |
| `core/models.py` | model | — | `core/threshold_manager.py` ThresholdState + `core/pool_state_manager.py` PoolState | exact |
| `core/usage_fetcher.py` | service | request-response | `core/usage_fetcher.py` (self — refactor) | exact |
| `monitoring/web_poller.py` | service | event-driven | `monitoring/orchestrator.py` MonitoringOrchestrator | role-match |
| `monitoring/orchestrator.py` | service | event-driven | `monitoring/orchestrator.py` (self — extend) | exact |
| `ui/display_controller.py` | controller | request-response | `ui/display_controller.py` (self — extend) | exact |
| `ui/session_display.py` | component | request-response | `ui/session_display.py` (self — extend) | exact |
| `cli/main.py` | controller | request-response | `cli/main.py` (self — extend) | exact |

---

## Pattern Assignments

### `pyproject.toml` — add keyring, browser-cookie3, httpx deps

**Analog:** `pyproject.toml` (self)

**Existing dependencies block** (lines 32–42):
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
  "tzdata"
]
```

**Change:** Append three new deps inside the existing list. Follow the same `"package>=version"` format with a blank-line comment group marker:
```toml
  # Phase 4 additions:
  "keyring>=25.0.0",
  "browser-cookie3>=0.19.1",
  "httpx>=0.27.0",
```

No other sections of pyproject.toml change. Do NOT add `curl_cffi` (deferred).

---

### `core/models.py` — add WebUsageData frozen dataclass

**Analog:** `core/threshold_manager.py` ThresholdState (lines 16–23) and `core/pool_state_manager.py` PoolState (lines 28–37)

**Existing frozen dataclass pattern** (threshold_manager.py lines 16–23):
```python
@dataclass(frozen=True)
class ThresholdState:
    """Result of one threshold evaluation cycle."""

    status: Literal["calibrating", "auto", "manual"]
    threshold_tokens: Optional[int]    # None when calibrating
    completed_session_count: int       # always populated (for display N/10)
    cold_start_minimum: int = 10       # informational — matches COLD_START_MINIMUM
```

**Existing frozen dataclass pattern** (pool_state_manager.py lines 28–37):
```python
@dataclass(frozen=True)
class PoolState:
    """Result of one pool spend evaluation cycle."""

    pool_size_usd: float
    pool_spend_usd: float
    pool_remaining_usd: float
    pool_pct_spent: float
    billing_cycle_start: str
    is_overage: bool
```

**Existing imports in models.py** (lines 1–8):
```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
```

**New dataclass to add** — append after existing classes, before `normalize_model_name()`:
```python
@dataclass(frozen=True)
class WebUsageData:
    """Authoritative usage data fetched from claude.ai API."""

    utilization_pct: float           # 0.0–100.0; from five_hour.utilization or extra_usage.utilization
    reset_at: datetime               # when this window/period resets (UTC)
    fetched_at: datetime             # when this data was retrieved (UTC)
    plan_limit_tokens: Optional[int]  # None for Teams (monthly_limit is cents, not tokens)
```

**Required import addition to models.py** — `timezone` is not needed (datetime is already imported); no new imports required for `WebUsageData` itself since `datetime` and `Optional` are already present.

---

### `core/usage_fetcher.py` — add Firefox cookies, keyring migration, refactor _read_auth_cookies(), add fetch_web_usage(), add _discover_org_id()

**Analog:** `core/usage_fetcher.py` (self — all changes are additive to this file)

**Existing imports block** (lines 16–26) — must add `httpx` import:
```python
import base64
import json
import logging
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional, Tuple
```
Add at top of new functions (lazy import style already used in `auto_seed_from_anthropic`): `import httpx` inside fetch functions, or add `import httpx` to the module-level imports.

**_USAGE_URL constant already present** (line 28):
```python
_USAGE_URL = "https://claude.ai/api/organizations/{org_id}/usage"
```
Add alongside it:
```python
_ACCOUNT_URL = "https://claude.ai/api/account"
```

**_USER_AGENT constant already present** (lines 29–33) — reuse as-is for all new HTTP calls.

**Existing _read_auth_cookies() to refactor** (lines 240–265):
```python
def _read_auth_cookies(config_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    cfg: dict = {}
    config_file = config_dir / "config.json"
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    except Exception as exc:
        logger.warning("usage_fetcher: failed to read config.json: %s", exc)

    session_key: Optional[str] = cfg.get("session_key") or None
    cf_clearance: Optional[str] = cfg.get("cf_clearance") or None

    if not session_key:
        logger.debug("usage_fetcher: session_key not in config — trying Chrome cookies")
        chrome_sk, chrome_cf = _read_chrome_cookies()
        session_key = session_key or chrome_sk
        cf_clearance = cf_clearance or chrome_cf

    return session_key, cf_clearance
```
Replace body entirely with the new priority-order version (see Shared Patterns section).

**Existing fetch_pool_spend_usd() — HTTP call pattern to mirror** (lines 272–313):
```python
def fetch_pool_spend_usd(org_id: str, config_dir: Path) -> Optional[float]:
    """Return current extra_usage spend in USD, or None on failure."""
    try:
        import urllib.request

        session_key, cf_clearance = _read_auth_cookies(config_dir)
        if not session_key:
            logger.warning("usage_fetcher: no sessionKey available (config or Chrome)")
            return None

        cookie_parts = [f"sessionKey={session_key}"]
        if cf_clearance:
            cookie_parts.append(f"cf_clearance={cf_clearance}")

        url = _USAGE_URL.format(org_id=org_id)
        req = urllib.request.Request(
            url,
            headers={
                "Cookie": "; ".join(cookie_parts),
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
                "anthropic-client-platform": "web_claude_ai",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        extra = body.get("extra_usage")
        ...
    except Exception as exc:
        logger.warning("usage_fetcher: request failed: %s", exc)
        return None
```
`fetch_web_usage()` uses `httpx` instead of `urllib.request` but follows the identical cookie assembly, header dict, and outer try/except structure. `_discover_org_id()` also uses `httpx`.

**Existing atomic write pattern** (auto_seed_from_anthropic, lines 344–356):
```python
tmp = config_file.with_suffix(".tmp")
tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
tmp.replace(config_file)
```
`_migrate_config_to_keyring()` must use this same `.tmp` → `.replace()` pattern when writing the cleaned config.json back.

---

### `monitoring/web_poller.py` — NEW file

**Analog:** `monitoring/orchestrator.py` MonitoringOrchestrator threading pattern (lines 18–73)

**Thread construction pattern from orchestrator** (lines 54–57):
```python
self._monitor_thread = threading.Thread(
    target=self._monitoring_loop, name="MonitoringThread", daemon=True
)
self._monitor_thread.start()
```
WebPoller subclasses `threading.Thread` directly (`class WebPoller(threading.Thread)`) with `daemon=True` set in `__init__` via `super().__init__(name="WebPollerThread", daemon=True)`. This is slightly different from the orchestrator which creates a Thread attribute — WebPoller IS the thread.

**Stop event pattern from orchestrator** (lines 35–37, 59–70):
```python
self._stop_event: threading.Event = threading.Event()
...
def stop(self) -> None:
    self._monitoring = False
    self._stop_event.set()
    if self._monitor_thread and self._monitor_thread.is_alive():
        self._monitor_thread.join(timeout=5)
```
WebPoller's `stop()` only calls `self._stop_event.set()` — no join needed because it is a daemon thread (dies with process).

**Loop pattern from orchestrator** (lines 123–138):
```python
def _monitoring_loop(self) -> None:
    self._fetch_and_process_data()       # initial fetch
    while self._monitoring:
        if self._stop_event.wait(timeout=self.update_interval):
            if not self._monitoring:
                break
        self._fetch_and_process_data()
```
WebPoller uses the simpler `while not self._stop_event.wait(300):` idiom — `wait()` returns `True` when stop is signaled, so `not True` exits the loop. Poll immediately on entry, then wait.

**Imports to use** (mirror orchestrator lines 1–15):
```python
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from claude_monitor.core.models import WebUsageData
from claude_monitor.core.usage_fetcher import fetch_web_usage
```

**Full class skeleton:**
```python
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
        logger.info("WebPoller: starting (300s interval)")
        self._poll_once()
        while not self._stop_event.wait(300):
            self._poll_once()
        logger.info("WebPoller: stopped")

    def stop(self) -> None:
        self._stop_event.set()

    def get_web_usage(self) -> Optional[WebUsageData]:
        with self._cache_lock:
            return self._web_usage

    def get_last_sync_time(self) -> Optional[datetime]:
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

---

### `monitoring/orchestrator.py` — add set_web_poller(), add web_usage to monitoring_data

**Analog:** `monitoring/orchestrator.py` (self — two additions)

**Pattern for set_args() method** (lines 74–80) — `set_web_poller()` follows the identical single-attribute-setter pattern:
```python
def set_args(self, args: Any) -> None:
    """Set command line arguments for token limit calculation."""
    self._args = args
```

**New method to add** — after `set_args()`:
```python
def set_web_poller(self, poller: "WebPoller") -> None:
    """Register the WebPoller instance for web usage data retrieval."""
    self._web_poller = poller
```
Add `self._web_poller: Optional["WebPoller"] = None` in `__init__` alongside the other instance attributes (lines 35–41).

**Add to monitoring_data dict** (lines 193–201) — the Phase 3 pool_state addition is the exact model to copy:
```python
# Phase 3 addition (existing):
"pool_state": pool_state,

# Phase 4 addition (new — add immediately after pool_state line):
"web_usage": self._web_poller.get_web_usage() if self._web_poller else None,
```

The orchestrator import block (lines 1–14) needs one addition:
```python
# add after existing imports:
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from claude_monitor.monitoring.web_poller import WebPoller
```
Or use a string annotation `"WebPoller"` in `set_web_poller()` to avoid circular import — the TYPE_CHECKING guard is the safest approach.

---

### `ui/display_controller.py` — add web_usage kwarg pass-through

**Analog:** `ui/display_controller.py` (self — two-line addition per Phase 3 pool_state pattern)

**Existing create_data_display() signature** (lines 203–210):
```python
def create_data_display(
    self,
    data: Dict[str, Any],
    args: Any,
    token_limit: int,
    threshold_state: Optional[ThresholdState] = None,  # Phase 2
    pool_state: Optional[PoolState] = None,             # Phase 3 NEW
) -> RenderableType:
```
Add `web_usage` parameter following the identical pattern:
```python
    web_usage: Optional["WebUsageData"] = None,         # Phase 4 NEW
```

**Existing processed_data kwarg injection** (lines 283–285) — the exact two-line pattern to replicate:
```python
# Phase 2: pass threshold_state through to session_display via kwargs
processed_data["threshold_state"] = threshold_state
# Phase 3: pass pool_state through to session_display via kwargs
processed_data["pool_state"] = pool_state
```
Add immediately after line 285:
```python
# Phase 4: pass web_usage through to session_display via kwargs
processed_data["web_usage"] = web_usage
```

**Import addition** — add to the existing imports block (lines 20–21):
```python
from claude_monitor.core.models import WebUsageData
```
(Already imports `normalize_model_name` from `core.models` at line 22, so just add `WebUsageData` to that import.)

---

### `ui/session_display.py` — add web data rows, fallback display rows

**Analog:** `ui/session_display.py` (self — add to `format_active_session_screen()`)

**Existing kwargs.get() pattern for threshold_state** (lines 270–271):
```python
threshold_state = kwargs.get("threshold_state")
if threshold_state is not None:
```

**Existing kwargs.get() pattern for pool_state** (lines 315–316):
```python
pool_state = kwargs.get("pool_state")
if (
    pool_state is not None
    and threshold_state is not None
    and threshold_state.status != "calibrating"
):
```

**web_usage block** — insert after the pool_state block (after line 355), before the closing `else:` at line 355. The Phase 4 web_usage block runs in the `if plan in ["custom", "pro", "max5", "max20"]:` branch, after pool_state:
```python
# Phase 4: Web usage rows (D-17, D-18, D-19)
web_usage = kwargs.get("web_usage")
if web_usage is not None:
    screen_buffer.append(f"[separator]{'─' * 60}[/]")
    util_bar = self._render_wide_progress_bar(web_usage.utilization_pct)
    screen_buffer.append(
        f"🌐 [value]Utilization:[/]         {util_bar} {web_usage.utilization_pct:.1f}%  [dim]via claude.ai[/]"
    )
    # Resets-in row (D-17)
    now = datetime.now(timezone.utc)
    delta = web_usage.reset_at - now
    total_secs = max(0, int(delta.total_seconds()))
    hours, rem = divmod(total_secs, 3600)
    mins = rem // 60
    screen_buffer.append(
        f"⏱  [value]Resets in:[/]           {hours}h {mins}m"
    )
    # Last sync footer (D-19)
    last_sync = kwargs.get("last_web_sync")
    if last_sync:
        screen_buffer.append(
            f"🔄 [dim]Last web sync: {last_sync.strftime('%H:%M:%S')}[/]"
        )
```

**D-18 fallback** — when `web_usage is None`, the existing threshold_state block already handles the P90 rows. The only addition for D-18 is appending `(est. — web unavailable)` to the threshold row label. This is done inside the `threshold_state` block at line 284, modifying the P90 row string conditionally:
```python
# D-18: append web-unavailable suffix when web_usage absent
web_unavailable_suffix = "" if kwargs.get("web_usage") is not None else " (est. — web unavailable)"
# then in the threshold row for status == "auto":
f"🎯 [value]Token limit:[/]          "
f"[info]{threshold_state.threshold_tokens:,} tokens[/] [dim](P90){web_unavailable_suffix}[/]"
```

**Import addition** — add `timezone` to the datetime import:
```python
from datetime import datetime, timezone
```
(Current line 7 only has `from datetime import datetime`.)

**_render_wide_progress_bar()** — already exists at lines 64–95. Reuse directly for the utilization bar.

---

### `cli/main.py` — auth setup flow, WebPoller start/stop wiring, pool reset log

**Analog:** `cli/main.py` (self — extensions to `_run_monitoring()` and `main()`)

**Existing startup call site in main()** (lines 82–98) — auth setup must run before `_run_monitoring()` is called. Pattern: insert calls between `init_timezone()` and `_run_monitoring(args)`:
```python
init_timezone(settings.timezone)

args = settings.to_namespace()

_run_monitoring(args)
```
Insert auth setup after `init_timezone()` and before `_run_monitoring()`.

**Existing try/finally block in _run_monitoring()** (lines 162–266) — the `finally` block at line 243:
```python
finally:
    # Stop monitoring first
    if "orchestrator" in locals():
        orchestrator.stop()
```
WebPoller stop follows the identical pattern:
```python
    if "web_poller" in locals():
        web_poller.stop()  # signals event; daemon thread exits on next wake
```

**Existing orchestrator start sequence** (lines 168–228):
```python
orchestrator = MonitoringOrchestrator(...)
orchestrator.set_args(args)
...
orchestrator.register_update_callback(on_data_update)
orchestrator.start()
```
WebPoller is instantiated and started before `orchestrator.start()`:
```python
web_poller = WebPoller(org_id, config_dir)
web_poller.start()
orchestrator.set_web_poller(web_poller)
orchestrator.start()
```

**Existing on_data_update() callback** (lines 177–210) — the Phase 3 kwarg addition is the exact pattern for Phase 4:
```python
renderable = display_controller.create_data_display(
    data,
    args,
    monitoring_data.get("token_limit", token_limit),
    threshold_state=monitoring_data.get("threshold_state"),
    pool_state=monitoring_data.get("pool_state"),          # Phase 3
)
```
Add:
```python
    web_usage=monitoring_data.get("web_usage"),            # Phase 4 NEW
```

**Auth setup flow placement** — must run BEFORE `live_display.__enter__()` at line 164. The blocking console prompt (D-08) cannot run inside a Rich Live context. Current code enters Live at line 164; auth setup goes into `_run_monitoring()` before line 164, or into a new helper function called from `main()` before `_run_monitoring()`.

**New imports to add to cli/main.py:**
```python
from claude_monitor.monitoring.web_poller import WebPoller
from claude_monitor.core.usage_fetcher import (
    _migrate_config_to_keyring,
    _read_auth_cookies,
    _discover_org_id,
    fetch_web_usage,
)
```

**D-24 pool reset log** — in `core/pool_state_manager.py`, `compute_pool_state()` already detects billing cycle changes via `_derive_billing_cycle_start()`. Add INFO log when the cycle_start changes between calls. Pattern to follow: inside `compute_pool_state()` after `cycle_start` is determined (lines 253–265), add:
```python
# D-24: log billing cycle reset event
if cached.get("billing_cycle_start") and cycle_start.isoformat() != cached.get("billing_cycle_start"):
    logger.info("Billing cycle reset — pool spend cleared to $0.00")
```

---

## Shared Patterns

### Frozen Dataclass
**Source:** `core/threshold_manager.py` (lines 16–23) and `core/pool_state_manager.py` (lines 28–37)
**Apply to:** `core/models.py` WebUsageData addition
```python
@dataclass(frozen=True)
class SomeName:
    """Result of one evaluation cycle."""
    field_name: type  # inline comment explaining semantics
    optional_field: Optional[type]
```

### Atomic Config Write
**Source:** `core/usage_fetcher.py` auto_seed_from_anthropic (lines 344–356) and `core/pool_state_manager.py` _write_pool_spend_cache (lines 206–219)
**Apply to:** `_migrate_config_to_keyring()` in usage_fetcher.py
```python
tmp = config_file.with_suffix(".tmp")
tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
tmp.replace(config_file)
```

### kwargs Pass-Through (threshold_state / pool_state model)
**Source:** `ui/display_controller.py` lines 282–285 and `ui/session_display.py` lines 270–271, 315–316
**Apply to:** `web_usage` kwarg in display_controller.create_data_display() and session_display.format_active_session_screen()
```python
# In display_controller.py create_data_display():
processed_data["web_usage"] = web_usage

# In session_display.py format_active_session_screen():
web_usage = kwargs.get("web_usage")
if web_usage is not None:
    ...
```

### Cookie Assembly + HTTP Request
**Source:** `core/usage_fetcher.py` fetch_pool_spend_usd (lines 272–313)
**Apply to:** `fetch_web_usage()` and `_discover_org_id()` in usage_fetcher.py
```python
cookie_parts = [f"sessionKey={session_key}"]
if cf_clearance:
    cookie_parts.append(f"cf_clearance={cf_clearance}")
# then headers dict with Cookie, Accept, User-Agent, anthropic-client-platform
```

### Daemon Thread Stop Event
**Source:** `monitoring/orchestrator.py` (lines 35–37, 59–70, 123–138)
**Apply to:** `monitoring/web_poller.py` WebPoller
```python
self._stop_event = threading.Event()
...
def stop(self) -> None:
    self._stop_event.set()
...
# in run():
while not self._stop_event.wait(300):   # wait() returns True when set() called
    self._poll_once()
```

### Error Handling (non-fatal warning + None return)
**Source:** `core/usage_fetcher.py` fetch_pool_spend_usd (lines 311–313)
**Apply to:** All new functions in usage_fetcher.py (`fetch_web_usage`, `_read_firefox_cookies`, `_discover_org_id`, `_migrate_config_to_keyring`)
```python
except Exception as exc:
    logger.warning("fetch_web_usage: request failed: %s", exc)
    return None
```

### Rich Progress Bar Reuse
**Source:** `ui/session_display.py` _render_wide_progress_bar (lines 64–95)
**Apply to:** web_usage utilization bar in session_display.py
```python
util_bar = self._render_wide_progress_bar(web_usage.utilization_pct)
# Returns: "🟢/🟡/🔴 [<styled bar>]"
```

### Finally Block Cleanup
**Source:** `cli/main.py` _run_monitoring finally block (lines 243–251)
**Apply to:** WebPoller stop in cli/main.py
```python
finally:
    if "orchestrator" in locals():
        orchestrator.stop()
    if "web_poller" in locals():
        web_poller.stop()
```

---

## No Analog Found

No files are without analog. All 8 files have strong same-role or exact-file analogs.

---

## Critical Implementation Notes (for Planner)

### Note 1: Auth prompt placement (Pitfall 5)
The blocking console prompt (D-08) must run **before** `live_display.__enter__()` at `cli/main.py` line 164. Do NOT place auth prompt inside the `try:` block that opens the Rich Live context. Auth setup belongs between `init_timezone()` and the `try:` block that calls `enter_alternate_screen()`.

### Note 2: _read_auth_cookies() replacement body
The existing body reads config.json first, then falls back to Chrome. The Phase 4 replacement body is:
```
Priority 1: keyring.get_password("claude-monitor", "sessionKey")
Priority 2: _read_firefox_cookies()
Priority 3: _read_chrome_cookies()  [existing function, no changes]
Priority 4: caller handles manual prompt
```
The existing `_read_chrome_cookies()` function is unchanged and moves to position 3.

### Note 3: five_hour null for Teams/Enterprise (Pitfall 1)
`fetch_web_usage()` must check `body.get("five_hour") is not None` before accessing sub-fields. For this account, `five_hour` is always `null`. Check `extra_usage` branch when `five_hour is None`.

### Note 4: keyring delete_password exception (Pitfall 3)
```python
try:
    keyring.delete_password("claude-monitor", "sessionKey")
except keyring.errors.PasswordDeleteError:
    pass
```

### Note 5: WebPoller requires org_id before construction (Pitfall 6)
`WebPoller(org_id, config_dir)` — org_id is a required positional argument. Auth setup and org_id discovery must complete before instantiating WebPoller.

### Note 6: extra_usage monetary fields are in CENTS (Pitfall 2)
`plan_limit_tokens` in WebUsageData should be `None` for Teams accounts. `monthly_limit: 75000` = $750.00. Do not divide `used_credits` by 100 for WebUsageData — `utilization` is already a percentage.

---

## Metadata

**Analog search scope:** `core/`, `monitoring/`, `ui/`, `cli/` directories
**Files read:** 11 source files
**Pattern extraction date:** 2026-05-18
