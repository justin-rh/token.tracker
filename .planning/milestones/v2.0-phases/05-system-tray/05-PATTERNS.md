# Phase 5: System Tray — Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 3 (1 new, 2 modified)
**Analogs found:** 3 / 3

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `ui/tray_manager.py` | service/wrapper | event-driven + request-response | `monitoring/web_poller.py` | role-match (daemon thread ownership, Lock pattern, start/stop API) |
| `cli/main.py` | controller | request-response | `cli/main.py` itself (WebPoller block) | exact (extend existing WebPoller wiring pattern) |
| `monitoring/web_poller.py` | service | event-driven | n/a — read-only analog | exact |

---

## Pattern Assignments

### `ui/tray_manager.py` (NEW — service/wrapper, event-driven)

**Primary analog:** `monitoring/web_poller.py`
**Secondary analog:** `ui/display_controller.py` (for ui/ module import style)

**Imports pattern** (`monitoring/web_poller.py` lines 21–30 + `ui/display_controller.py` lines 1–37):

```python
"""System tray icon manager for Token Tracker.

Wraps pystray Icon lifecycle. Exposes start(), stop(), update().
Threading model (per STATE.md):
  - Tray: icon.run_detached() from main thread — NOT a 4th thread
  - update() called from MonitoringThread via on_data_update callback
"""
import ctypes
import logging
import os
import signal
import threading
from datetime import datetime
from typing import Optional

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)
```

Note: `logger = logging.getLogger(__name__)` is the module-level logger pattern used in every existing module (web_poller.py line 30, orchestrator.py line 15, display_controller.py implicit via logging import).

**Lock/shared-state pattern** (`monitoring/web_poller.py` lines 55–70):

```python
# web_poller.py — exact pattern to copy for TrayManager internal state
self._stop_event: threading.Event = threading.Event()
self._cache_lock: threading.Lock = threading.Lock()
self._web_usage: Optional[WebUsageData] = None
self._last_sync_time: Optional[datetime] = None
```

TrayManager equivalent:
```python
self._icon: Optional[pystray.Icon] = None
self._lock = threading.Lock()   # guards icon.icon + icon.title updates
```

**Thread-safe read/write pattern** (`monitoring/web_poller.py` lines 94–109):

```python
# web_poller.py — Lock acquire on both read and write
def get_web_usage(self) -> Optional[WebUsageData]:
    with self._cache_lock:
        return self._web_usage

def _poll_once(self) -> None:
    result = fetch_web_usage(self._org_id, self._config_dir)
    if result is not None:
        with self._cache_lock:
            self._web_usage = result
            self._last_sync_time = datetime.now(timezone.utc)
```

Copy this pattern for `TrayManager.update()`:
```python
def update(self, utilization_pct: Optional[float], last_sync: Optional[datetime]) -> None:
    if self._icon is None:
        return
    with self._lock:
        self._icon.icon = self._make_icon_image(utilization_pct or 0.0)
        self._icon.title = self._build_tooltip(utilization_pct, last_sync)
```

**stop() pattern** (`monitoring/web_poller.py` lines 85–92):

```python
# web_poller.py — stop signals the event, returns immediately, no join
def stop(self) -> None:
    """Signal the poller to stop. Returns immediately."""
    logger.debug("WebPoller: stop signal sent")
    self._stop_event.set()
```

TrayManager equivalent (no Event needed — pystray owns the loop):
```python
def stop(self) -> None:
    """Stop the pystray icon cleanly. Safe to call if not started."""
    if self._icon is not None:
        self._icon.stop()
```

**None-guard before start** (`cli/main.py` lines 188–193 and 265–270):

```python
# cli/main.py — guard on org_id before constructing WebPoller; guard in finally
web_poller = None
if org_id:
    web_poller = WebPoller(org_id, config_dir)
    web_poller.start()
    orchestrator.set_web_poller(web_poller)

# In finally:
if "web_poller" in locals() and web_poller is not None:
    web_poller.stop()
```

Copy this exact guard idiom for tray_manager in `cli/main.py`.

**ui/ module header pattern** (`ui/session_display.py` lines 1–25):

```python
"""Session display components for Claude Monitor.

Handles formatting of active session screens and session data display.
"""
from dataclasses import dataclass
from datetime import datetime
...
from claude_monitor.ui.components import ...
from claude_monitor.ui.layouts import ...
```

`ui/tray_manager.py` is a standalone class with no imports from other `ui/` submodules — module docstring + stdlib imports + pystray/Pillow is the full import block.

---

### `cli/main.py` (MODIFY — controller, request-response)

**Analog section:** `cli/main.py` lines 186–270 (the existing WebPoller wiring block — copy this structure exactly, adding TrayManager beside it)

**Init pattern** (lines 186–193) — copy and extend:

```python
# Existing WebPoller block (lines 186–193):
web_poller = None
if org_id:
    web_poller = WebPoller(org_id, config_dir)
    web_poller.start()
    orchestrator.set_web_poller(web_poller)

# ADD immediately after (same pattern):
tray_manager = TrayManager(shutdown_callback=_tray_shutdown)
tray_manager.start()
```

**on_data_update callback injection point** (lines 195–226):

```python
# Existing callback (lines 195–226) already builds monitoring_data.
# ADD tray update at the end of the try block, after live_display.update():
web_usage = monitoring_data.get("web_usage")
if tray_manager is not None:
    tray_manager.update(
        utilization_pct=web_usage.utilization_pct if web_usage else None,
        last_sync=monitoring_data.get("last_web_sync"),
    )
```

**finally block pattern** (lines 263–275) — copy and extend:

```python
# Existing finally block (lines 263–275):
finally:
    if "orchestrator" in locals():
        orchestrator.stop()
    if "web_poller" in locals() and web_poller is not None:
        web_poller.stop()
    if live_display_active:
        with contextlib.suppress(Exception):
            live_display.__exit__(None, None, None)

# ADD tray stop (same guard pattern as web_poller):
    if "tray_manager" in locals() and tray_manager is not None:
        tray_manager.stop()
```

**Shutdown signal helper** — place immediately before `_run_monitoring()` function or as a local def inside it:

```python
import os
import signal as _signal  # already imported at line 6

def _tray_shutdown() -> None:
    """Trigger clean shutdown from pystray thread (identical to Ctrl+C).
    Per RESEARCH.md Pitfall 2-3: use CTRL_C_EVENT not SIGINT on Windows.
    """
    os.kill(os.getpid(), _signal.CTRL_C_EVENT)
```

Note: `signal` is already imported at line 6 of `cli/main.py`. Use the existing import — do not add a duplicate.

**Import additions for cli/main.py:**

```python
# Add after existing monitoring/web_poller import (line 30):
from claude_monitor.ui.tray_manager import TrayManager
```

---

### `monitoring/web_poller.py` (READ-ONLY ANALOG — not modified in Phase 5)

This file is the primary structural analog for `ui/tray_manager.py`. It is not modified in Phase 5. Its patterns are documented in the TrayManager section above.

The key data path from web_poller to tray:
- `monitoring_data["web_usage"]` → `WebUsageData.utilization_pct` (float, 0–100)
- `monitoring_data["last_web_sync"]` → `datetime` (UTC, may be None)

Both are already present in `orchestrator.py` lines 211–212:
```python
"web_usage": self._web_poller.get_web_usage() if self._web_poller else None,
"last_web_sync": self._web_poller.get_last_sync_time() if self._web_poller else None,
```

No changes to `web_poller.py` or `orchestrator.py` are needed for Phase 5.

---

## Shared Patterns

### Logging
**Source:** Every module (`monitoring/web_poller.py` line 30, `monitoring/orchestrator.py` line 15)
**Apply to:** `ui/tray_manager.py`

```python
import logging
logger = logging.getLogger(__name__)
```

Use `logger.info()` in `start()` and `stop()`. Use `logger.debug()` in `update()` to avoid log spam on every monitoring cycle.

### None-guard + locals() check in finally
**Source:** `cli/main.py` lines 265–270
**Apply to:** TrayManager stop call in `cli/main.py` finally block

```python
if "tray_manager" in locals() and tray_manager is not None:
    tray_manager.stop()
```

This pattern is already established for WebPoller — copy it exactly. It handles the case where `tray_manager` was never assigned (e.g., exception before the assignment line).

### Thread-safe property update with Lock
**Source:** `monitoring/web_poller.py` lines 94–109 (get + set under same Lock)
**Apply to:** `TrayManager.update()` method

```python
with self._lock:
    self._icon.icon = self._make_icon_image(utilization_pct or 0.0)
    self._icon.title = self._build_tooltip(utilization_pct, last_sync)
```

### pyproject.toml dependency addition pattern
**Source:** `pyproject.toml` lines 43–46 (Phase 4 additions block)

```toml
# Phase 4 additions (lines 43–46):
"keyring>=25.0.0",
"browser-cookie3>=0.19.1",
"httpx>=0.27.0",

# Phase 5 additions — add after:
"pystray>=0.19.5",
"Pillow>=12.0.0",
```

Follow the same comment-labeled block pattern used for Phase 4 additions.

---

## No Analog Found

No files in this phase lack an analog. All three files have established patterns to copy from:

| File | Analog Quality | Notes |
|------|---------------|-------|
| `ui/tray_manager.py` | role-match | WebPoller provides the threading/Lock/start/stop skeleton; pystray API from RESEARCH.md fills the body |
| `cli/main.py` | exact | Extend the existing WebPoller block — TrayManager wiring is structurally identical |
| `monitoring/web_poller.py` | n/a (not modified) | Read-only data source for Phase 5 |

---

## Metadata

**Analog search scope:** `monitoring/`, `ui/`, `cli/`, `pyproject.toml`
**Files read:** `monitoring/web_poller.py`, `cli/main.py`, `monitoring/orchestrator.py`, `ui/session_display.py`, `ui/display_controller.py`, `pyproject.toml`
**Pattern extraction date:** 2026-05-19
