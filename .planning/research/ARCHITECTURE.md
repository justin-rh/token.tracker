# Architecture: v2.0 Integration Plan

**Project:** Claude Token Tracker  
**Milestone:** v2.0 — Web-Sourced Usage + System Tray  
**Researched:** 2026-05-18  
**Confidence:** HIGH — based on direct codebase inspection

---

## Current Architecture (v1.0)

### Entry Point Chain

```
monitor.py
  → cli/main.py::main()
      → cli/main.py::_run_monitoring()
          → MonitoringOrchestrator (monitoring/orchestrator.py)
              → DataManager (monitoring/data_manager.py)
                  → analyze_usage() (data/analysis.py)
                      → load_usage_entries() (data/reader.py)
              → ThresholdManager (core/threshold_manager.py)
              → compute_pool_state() (core/pool_state_manager.py)
          → DisplayController (ui/display_controller.py)
              → SessionDisplayComponent (ui/session_display.py)
```

### Threading Model (v1.0)

| Thread | Name | Role |
|--------|------|------|
| Main | MainThread | Owns Rich `Live` display, loops on `time.sleep(1)` (Windows signal.pause fallback) |
| Background | MonitoringThread | `MonitoringOrchestrator._monitoring_loop()` — reads JSONL, calls callbacks |

Callbacks from `MonitoringThread` cross into `MainThread` via `live_display.update(renderable)`. Rich `Live` is thread-safe for `.update()` calls.

### Data Flow (v1.0)

```
JSONL files (%APPDATA%\.claude\projects\*\*.jsonl)
  → data/reader.py::load_usage_entries()  [dedup by requestId]
  → data/analysis.py::analyze_usage()     [aggregate into blocks]
  → DataManager cache (5s TTL)
  → MonitoringOrchestrator._fetch_and_process_data()
      applies: ThresholdState, PoolState, token_limit
      emits: monitoring_data dict
  → on_data_update() callback in cli/main.py
  → DisplayController.create_data_display()
  → live_display.update(renderable)
```

### Config and Persistence

| File | Location | Purpose |
|------|----------|---------|
| `config.json` | `~/.claude-monitor/config.json` | Pool size, billing cycle day, org_id, session_key, cf_clearance, auto_seed flag |
| `pool_spend.json` | `~/.claude-monitor/pool_spend.json` | Atomic cache of pool spend + billing cycle start |
| `last_used.json` | `~/.claude-monitor/last_used.json` | Last CLI settings (theme, timezone, etc.) |

### Key Modules and Responsibilities

| Module | Responsibility | Status for v2.0 |
|--------|---------------|-----------------|
| `monitor.py` | UTF-8 + VTP bootstrap, delegates to cli/main.py | Unchanged |
| `cli/main.py` | Arg parsing, thread setup, callback wiring | Modified — start tray and web poller |
| `cli/bootstrap.py` | Dirs, logging, timezone, `auto_seed_pool_spend()` | Unchanged — already calls usage_fetcher |
| `monitoring/orchestrator.py` | JSONL polling loop, callback dispatch | Modified — add web_usage to monitoring_data |
| `monitoring/data_manager.py` | JSONL fetch + 5s TTL cache | Unchanged |
| `core/usage_fetcher.py` | Cookie extraction, HTTP fetch to usage API | Extended — add fetch_web_usage() |
| `core/pool_state_manager.py` | Pool spend computation, persistence | Modified — accept WebUsageData override |
| `core/threshold_manager.py` | P90 inference | Unchanged |
| `core/models.py` | Frozen dataclasses | Add WebUsageData dataclass |
| `ui/display_controller.py` | Renders monitoring_data to Rich renderable | Modified — pass web_usage through |
| `ui/session_display.py` | Terminal dashboard rows | Modified — add web-sourced rows |

---

## Critical Pre-Existing Code

**`core/usage_fetcher.py` already exists and is already integrated.**

This is the most important fact for planning. The module implements:
- Chrome DPAPI + AES-GCM v10/v11 cookie decryption (fully working on Windows)
- Shared-access file copy so Chrome's locked cookie DB can be read while Chrome is closed
- Detection of whether Chrome is running (falls back to config.json values when Chrome is open)
- HTTP fetch to `https://claude.ai/api/organizations/{org_id}/usage`
- Parsing of `extra_usage.used_credits` as the authoritative pool spend seed
- `auto_seed_from_anthropic()` called at startup via `cli/bootstrap.py::auto_seed_pool_spend()`

The v2.0 "cookie extractor" and "web fetcher" components are therefore not new modules — they are extensions of existing code. The auth, HTTP, and crypto layers are done. What is missing is a richer return type, a background polling loop, and the system tray.

---

## New Components

### 1. `WebUsageData` dataclass in `core/models.py`

New frozen dataclass alongside existing ones. Zero new imports required — uses only `datetime` and `Optional` already imported.

```python
@dataclass(frozen=True)
class WebUsageData:
    """Authoritative usage data fetched from claude.ai settings API."""
    plan_limit_tokens: Optional[int]   # authoritative included-token limit (if exposed by API)
    overage_usd: float                 # authoritative extra_usage.used_credits in USD
    billing_period_start: str          # ISO date string from API or config billing cycle
    fetched_at: datetime               # UTC timestamp of last successful fetch
```

This is a pure addition — no existing fields or classes change.

### 2. `fetch_web_usage()` in `core/usage_fetcher.py`

An extension of the existing `fetch_pool_spend_usd()` function. The existing function is called at startup to seed `pool_spend.json`. The new function is called by the background poller every 5 minutes and returns a `WebUsageData` object.

The auth layer (`_read_auth_cookies()`) and HTTP client (`urllib.request`) are already there. The new function reuses both; it just parses additional fields from the same API response.

**Phase-specific research flag:** Inspect the actual API response shape before finalizing `WebUsageData` fields. The known field is `extra_usage.used_credits`. Whether `plan_limit_tokens` is exposed in this response needs live API verification at the start of Phase 4.

### 3. `monitoring/web_poller.py` — New Module

A thin background polling wrapper. Not a full orchestrator — a timer thread with a lock-protected result cache.

```
WebPoller
  interval: int (default 300 seconds)
  _thread: daemon=True, name="WebPollerThread"
  _last_result: Optional[WebUsageData]
  _lock: threading.Lock

  start() — spawns WebPollerThread
  stop()  — signals thread to stop, joins with timeout
  get_latest() -> Optional[WebUsageData]  — non-blocking, returns cached result
```

**Why separate from MonitoringOrchestrator:**
The orchestrator loop runs at `update_interval` (default 10s). Web fetches at 5-minute intervals must not block or be blocked by the JSONL read cycle. A separate poller with its own sleep cycle keeps concerns isolated and prevents a slow HTTP call from delaying JSONL reads. The orchestrator calls `web_poller.get_latest()` (non-blocking) on every JSONL cycle.

### 4. `ui/tray_manager.py` — New Module

Wraps `pystray` in a daemon thread.

```
TrayManager
  _icon: pystray.Icon
  _thread: daemon=True, name="TrayThread"

  start()                       — spawns TrayThread; blocks that thread with icon.run()
  stop()                        — calls icon.stop(); TrayThread exits
  update_state(pct_used: float) — maps percentage to icon color:
                                    pct_used < 50.0  → green  (0, 200, 0)
                                    pct_used < 75.0  → yellow (220, 180, 0)
                                    pct_used >= 75.0 → red    (220, 0, 0)
```

Icon image generated at runtime using `Pillow.ImageDraw` — a small circle on a transparent background. No external image file needed.

**pystray threading contract:** `pystray.Icon.run()` blocks the calling thread. It must be called from a dedicated daemon thread, never from `MainThread` (owns Rich Live) or `MonitoringThread`. This is the reason for a third named thread.

---

## Integration Points

### Point 1: `cli/main.py::_run_monitoring()` — Web Poller Startup

After `orchestrator.start()`, instantiate `WebPoller` and pass it to the orchestrator:

```python
web_poller = WebPoller(interval=300)
web_poller.start()
orchestrator.set_web_poller(web_poller)
```

Stop it in the `finally` block alongside `orchestrator.stop()`.

### Point 2: `cli/main.py::_run_monitoring()` — Tray Startup

After `web_poller.start()`, instantiate and start `TrayManager`. Register a second callback:

```python
tray = TrayManager()
tray.start()

def on_tray_update(monitoring_data: Dict[str, Any]) -> None:
    pool_state = monitoring_data.get("pool_state")
    if pool_state:
        tray.update_state(pool_state.pool_pct_spent)

orchestrator.register_update_callback(on_tray_update)
```

Stop it in the `finally` block.

### Point 3: `monitoring/orchestrator.py::_fetch_and_process_data()` — Attach Web Data

After JSONL data is fetched and validated, call `self._web_poller.get_latest()` (non-blocking):

```python
web_usage = self._web_poller.get_latest() if self._web_poller else None
monitoring_data["web_usage"] = web_usage
```

All existing keys in `monitoring_data` are unchanged. `web_usage` is additive.

Add `set_web_poller()` method to `MonitoringOrchestrator`:

```python
def set_web_poller(self, poller: "WebPoller") -> None:
    self._web_poller = poller
```

Initialize `self._web_poller = None` in `__init__`.

### Point 4: `core/pool_state_manager.py::compute_pool_state()` — Web-Authoritative Override

Add optional `web_usage: Optional[WebUsageData] = None` parameter. When provided:
- Use `web_usage.overage_usd` as the pool spend seed instead of the file-sourced `pool_spend_seed_usd`
- Use `web_usage.billing_period_start` as the billing cycle start instead of the derived value (if available)

This keeps `pool_state_manager.py` as the single source of truth. The web value is injected, not hard-wired.

The existing `compute_pool_state(blocks, threshold_state)` signature gains a third optional param — no call sites break.

### Point 5: `ui/display_controller.py` and `ui/session_display.py` — Web Data Display

`create_data_display()` already accepts `threshold_state` and `pool_state` as keyword arguments. Add `web_usage: Optional[WebUsageData] = None` with the same pattern.

Pass it through to `session_display.format_active_session_screen()`.

The display layer uses `web_usage` to:
- Show an authoritative plan token limit row (when `plan_limit_tokens` is available)
- Show a "synced from claude.ai" label on the pool spend row
- Show "last synced X minutes ago" using `web_usage.fetched_at`

All existing display rows are unchanged. Web data is additive — shown alongside JSONL-estimated values.

---

## Data Flow Changes

### v1.0 Data Flow

```
JSONL files → reader → analysis → DataManager → Orchestrator
                                                    |
                                               ThresholdState
                                               PoolState (seeded from config.json)
                                                    |
                                             monitoring_data dict
                                                    |
                                          DisplayController → Rich Live
```

### v2.0 Data Flow

```
JSONL files → reader → analysis → DataManager → Orchestrator <── WebPoller.get_latest()
                                                    |                      ^
                                               ThresholdState     WebPollerThread
                                               PoolState (web-seeded when available)  (every 300s)
                                               WebUsageData (Optional)          ^
                                                    |            usage_fetcher.fetch_web_usage()
                                             monitoring_data dict           ^
                                                    |          claude.ai/api/.../usage (HTTPS)
                                          DisplayController → Rich Live
                                                    |
                                          on_tray_update() → TrayManager.update_state()
                                                                       |
                                                                  TrayThread
                                                              (pystray blocking)
```

### New Keys in `monitoring_data`

| Key | Type | New in v2.0 |
|-----|------|-------------|
| `data` | `Dict` | No |
| `token_limit` | `int` | No |
| `threshold_state` | `ThresholdState \| None` | No |
| `pool_state` | `PoolState` | No |
| `args` | `Namespace` | No |
| `session_id` | `str` | No |
| `session_count` | `int` | No |
| `web_usage` | `WebUsageData \| None` | **Yes** |

---

## Threading Model

### v2.0 Threads

| Thread | Name | Owner | Daemon | Blocking call |
|--------|------|-------|--------|---------------|
| Main | MainThread | Python runtime | No | `time.sleep(1)` loop (Windows) |
| JSONL Monitor | MonitoringThread | `MonitoringOrchestrator` | Yes | `_stop_event.wait(update_interval)` |
| Web Poller | WebPollerThread | `WebPoller` | Yes | `_stop_event.wait(300)` |
| System Tray | TrayThread | `TrayManager` | Yes | `pystray.Icon.run()` — blocks forever |

### Thread Safety Rules

1. `WebPoller._last_result` is protected by `threading.Lock`. `MonitoringThread` reads via `get_latest()` (acquires lock, returns value, releases). `WebPollerThread` writes after a successful fetch (acquires lock, assigns new frozen dataclass, releases). Assignment of a new object is atomic in CPython, but the lock is present for correctness regardless.

2. `TrayManager.update_state()` is called from `MonitoringThread` (via callback). `pystray.Icon.icon = new_image` is thread-safe per pystray's design — it posts to the Win32 message queue rather than writing directly.

3. `MainThread` never touches `WebPoller` or `TrayManager` directly after setup. The callbacks in `on_data_update` and `on_tray_update` run from `MonitoringThread`.

4. Rich `Live.update()` is called from `MonitoringThread` via callback — identical to the v1.0 pattern, unchanged.

### Daemon Thread Lifecycle and Shutdown

All three background threads are daemon threads. The `finally` block in `_run_monitoring()` stops them explicitly in dependency order before relying on daemon cleanup:

```
KeyboardInterrupt
  → finally block in _run_monitoring()
      orchestrator.stop()   # sets _stop_event, joins MonitoringThread (timeout=5s)
      web_poller.stop()     # sets _stop_event, joins WebPollerThread (timeout=5s)
      tray.stop()           # calls icon.stop(), TrayThread exits its blocking run()
      live_display.__exit__()
  → restore_terminal()
```

`tray.stop()` after `orchestrator.stop()` ensures no `update_state()` call races against the icon teardown.

---

## What Changes vs What Stays the Same

### Unchanged Modules

- `monitor.py` — UTF-8/VTP bootstrap
- `monitoring/data_manager.py` — JSONL cache and fetch
- `monitoring/session_monitor.py` — session tracking
- `core/threshold_manager.py` — P90 calculation
- `core/plans.py`, `core/pricing.py`, `core/calculations.py` — plan and pricing logic
- `data/reader.py`, `data/analysis.py`, `data/analyzer.py` — JSONL pipeline
- `terminal/manager.py`, `terminal/themes.py` — terminal utilities
- `utils/` — all utilities
- `cli/bootstrap.py` — already calls `auto_seed_from_anthropic()`, no change needed
- `core/settings.py` — no new CLI args required for tray or web poller

### Modified Modules (additive only — no breaking changes to existing signatures)

| Module | Change |
|--------|--------|
| `core/models.py` | Add `WebUsageData` frozen dataclass |
| `core/usage_fetcher.py` | Add `fetch_web_usage() -> Optional[WebUsageData]`; existing functions unchanged |
| `core/pool_state_manager.py` | Add optional `web_usage` param to `compute_pool_state()`; uses web values when present |
| `monitoring/orchestrator.py` | Add `set_web_poller()`; add `self._web_poller = None` in `__init__`; add `web_usage` key to `monitoring_data` |
| `cli/main.py::_run_monitoring()` | Instantiate `WebPoller` and `TrayManager`; register `on_tray_update` callback; stop both in `finally` |
| `ui/display_controller.py` | Add `web_usage` param to `create_data_display()`; pass through to session_display |
| `ui/session_display.py` | Add web-sourced rows: authoritative limit (if available), sync timestamp, "live from claude.ai" label on pool spend |

### New Modules

| Module | Purpose |
|--------|---------|
| `monitoring/web_poller.py` | 5-minute daemon polling thread; thread-safe `WebUsageData` cache |
| `ui/tray_manager.py` | pystray daemon thread wrapper; Pillow-generated color-coded circle icon |

---

## Circular Import Analysis

Current import graph for new additions:

- `monitoring/web_poller.py` imports `core/usage_fetcher.py` and `core/models.py` — both are leaf modules with no back-references into `monitoring/`. No cycle.
- `ui/tray_manager.py` imports `pystray` and `PIL` only — zero project imports. No cycle possible.
- `monitoring/orchestrator.py` imports `monitoring/web_poller.py` — orchestrator already imports from `monitoring/`; `web_poller.py` does not import from `orchestrator.py`. No cycle.
- `core/models.py` adding `WebUsageData` — no new imports needed. No cycle.
- `core/pool_state_manager.py` accepting `WebUsageData` — needs `from claude_monitor.core.models import WebUsageData`. `models.py` does not import `pool_state_manager.py`. No cycle.
- `ui/display_controller.py` accepting `WebUsageData` — same import path. No cycle.

No circular imports introduced by any v2.0 change.

---

## Suggested Build Order

Build order respects three dependency constraints:
1. Data model (`WebUsageData`) must exist before any module that types against it
2. `fetch_web_usage()` must exist before `WebPoller` can call it
3. `TrayManager` can be built in isolation but should be wired last (depends on `pool_state` being in `monitoring_data`, which is already there from v1.0)

### Phase 4: Web Data Foundation

**Goal:** Fetch authoritative pool spend from claude.ai and surface it in the terminal dashboard. No tray in this phase.

**Step 4.1 — `core/models.py`: add `WebUsageData`**
Zero-dependency change. Unblocks all downstream steps. Add alongside existing dataclasses; no existing code changes. Write no tests (it is a dataclass with no logic).

**Step 4.2 — `core/usage_fetcher.py`: add `fetch_web_usage()`**
Reuses existing `_read_auth_cookies()` and `urllib.request` pattern from `fetch_pool_spend_usd()`. Returns `Optional[WebUsageData]` on success, `None` on any failure. Confirm actual API response fields against a live call before finalizing the field list. Write unit tests with a mocked `urllib.request.urlopen`.

**Step 4.3 — `monitoring/web_poller.py`: create `WebPoller`**
Daemon thread with `threading.Event` for stop signaling and `threading.Lock` for result protection. Calls `fetch_web_usage()` on first wake and every `interval` seconds thereafter. Write unit tests for: thread starts and stops cleanly; `get_latest()` returns `None` before first fetch; `get_latest()` returns cached result after successful fetch; fetch failure leaves prior result intact.

**Step 4.4 — `monitoring/orchestrator.py`: add `set_web_poller()` and `web_usage` key**
Two-line change: `self._web_poller = None` in `__init__`, and `monitoring_data["web_usage"] = self._web_poller.get_latest() if self._web_poller else None` in `_fetch_and_process_data()`. Existing behavior is completely unchanged when `_web_poller` is `None`.

**Step 4.5 — `core/pool_state_manager.py`: accept `web_usage` override**
Add `web_usage: Optional[WebUsageData] = None` to `compute_pool_state()`. When `web_usage` is not `None`, use its `overage_usd` as the seed and its `billing_period_start` as the cutoff. Update existing unit tests to pass `web_usage=None` explicitly; add new test cases for the web-present branch.

**Step 4.6 — `cli/main.py`: wire WebPoller**
Instantiate, start, pass to orchestrator, stop in `finally`. Pass `web_usage` from `monitoring_data` into `display_controller.create_data_display()`.

**Step 4.7 — `ui/display_controller.py` + `ui/session_display.py`: web rows**
Add `web_usage` keyword argument through the display pipeline. Add display rows: "Synced from claude.ai: X min ago", authoritative pool spend when `web_usage.overage_usd` is present, plan limit row when `web_usage.plan_limit_tokens` is available.

**Checkpoint:** Terminal dashboard shows pool spend sourced from the web (with "live from claude.ai" label) rather than JSONL cost estimates. Last-sync timestamp visible. JSONL per-project breakdown unchanged.

---

### Phase 5: System Tray

**Goal:** Persistent Windows system tray icon that reflects current pool usage state.

**Step 5.1 — `ui/tray_manager.py`: create `TrayManager`**
`Pillow.Image.new("RGBA", (64, 64), (0, 0, 0, 0))` + `ImageDraw.ellipse()` to generate the icon. `pystray.Icon("claude-tracker", image, menu=...)` with a right-click menu containing "Quit". `icon.run()` in daemon thread. `update_state()` regenerates the Pillow image and sets `icon.icon = new_image`. Write unit tests for color thresholds (mock pystray.Icon).

**Step 5.2 — `cli/main.py`: wire TrayManager**
Instantiate and start after `web_poller.start()`. Register `on_tray_update` callback that reads `pool_state.pool_pct_spent` from `monitoring_data` and calls `tray.update_state()`. Add `tray.stop()` to `finally` block.

**Step 5.3 — Right-click menu (optional enhancement)**
Add "Open terminal" menu item (subprocess to launch a new terminal running monitor.py). Low-risk enhancement after basic tray is working.

**Checkpoint:** Tray icon visible in Windows system tray, green/yellow/red based on pool spend percentage, updates on every JSONL cycle (~10s). Web-sourced overage feeds the color when available.

---

### Phase 6: Hybrid Display Merger (evaluate after Phase 4)

The JSONL pipeline already provides per-project breakdown via `data["blocks"]`. Whether a dedicated `data/web_merger.py` is needed depends on display complexity after Phase 4.

**Decision rule:** If combining `web_usage` totals with JSONL block data requires more than ~30 lines in `session_display.py`, extract a `data/web_merger.py`. If it stays simple (a few conditional display rows), keep it inline. Make this call at the start of Phase 4, step 7.

---

## Key Constraints

### Chrome App-Bound Encryption (Chrome 127+)

Already handled in `usage_fetcher.py`. When Chrome is running, the DB is locked and `_read_chrome_cookies()` returns `(None, None)`. The code falls back to manually configured `session_key`/`cf_clearance` values in `config.json`. This constraint is fully mitigated. No new work required.

### API Response Shape Uncertainty

`fetch_pool_spend_usd()` reads `body["extra_usage"]["used_credits"]`. For `fetch_web_usage()`, additional fields (plan limit tokens, billing period start) need to be confirmed against a live API call. This is a **phase-specific research step** at the start of Phase 4, step 4.2 — do not finalize `WebUsageData` fields from assumptions alone.

### pystray Windows Requirements

`pystray` on Windows uses a hidden Win32 message window. `icon.run()` must be called from a non-main thread. The daemon thread pattern described above is pystray's documented Windows pattern. Rich Live writes to stdout/ANSI — the Win32 message loop is unrelated and there is no interference.

### Graceful Degradation

If `org_id` is not configured in `config.json`, `fetch_web_usage()` returns `None`. The `WebPoller._last_result` stays `None`. The orchestrator attaches `web_usage=None` to `monitoring_data`. All display and pool computation falls back to JSONL-only behavior — identical to v1.0. The tray still works, using JSONL-computed `pool_state.pool_pct_spent`.

This means v2.0 is fully backward compatible: users who have not configured `org_id` continue to see the v1.0 dashboard with no degradation.
