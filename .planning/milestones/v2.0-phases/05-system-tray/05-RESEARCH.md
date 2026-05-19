# Phase 5: System Tray — Research

**Researched:** 2026-05-19
**Domain:** pystray 0.19.5 (Windows win32 backend) + Pillow 12.x + ctypes Windows API
**Confidence:** HIGH

---

## Summary

Phase 5 adds a persistent color-coded system tray icon to the already-running token tracker. The full Phase 4 infrastructure (WebPoller daemon thread, WebUsageData cache, orchestrator.monitoring_data pipeline) is in place and verified working. This phase is purely additive: a single new module `ui/tray_manager.py` plus integration wiring in `cli/main.py`.

The architecture decision is locked: pystray `Icon.run_detached()` — not `run()`, not a daemon thread. Source inspection of the pystray 0.19.5 win32 backend reveals that `_run_detached()` internally spawns a `threading.Thread(target=lambda: self._run()).start()`. This means the tray runs its own OS message loop in a background thread — no main thread involvement required. The main thread remains free for the Rich Live display loop unchanged.

The tray icon reads `utilization_pct` from `WebPoller.get_web_usage()` (thread-safe, Lock-protected) to determine color, and sets `icon.icon = new_image` and `icon.title = new_tooltip` to update color and tooltip while running. `icon.stop()` posts `WM_STOP` to the win32 message loop, causing `_mainloop()` to exit its `finally` block which calls `_hide()` (NIM_DELETE) — this is clean, no ghost icons from proper `stop()` calls.

For left-click terminal toggle (TRAY-04), the win32 backend calls `Icon.__call__()` on `WM_LBUTTONUP`, which invokes `Menu.__call__()`, which finds and calls the first `MenuItem` with `default=True`. The ctypes pattern `GetConsoleWindow()` + `IsWindowVisible()` + `ShowWindow()` is the standard Windows API approach.

**Primary recommendation:** Create `ui/tray_manager.py` as a self-contained class that owns the pystray Icon lifecycle. Initialize it in `cli/main.py` after `_setup_auth()`, call `tray.start()` (which calls `icon.run_detached()` and sets `icon.visible = True`), and call `tray.stop()` in the existing `finally` block alongside `web_poller.stop()`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRAY-01 | Persistent tray icon, color-coded: green <50%, yellow 50-75%, red >75% utilization | Pillow `Image.new` + `ImageDraw.ellipse` creates 64x64 colored circle; `icon.icon = new_image` updates while running; color thresholds map exactly to WebUsageData.utilization_pct |
| TRAY-02 | Tooltip: current utilization % + last web sync time | `pystray.Icon(title=...)` constructor param; `icon.title = new_str` updates while running; maps to NIF_TIP in win32 backend |
| TRAY-03 | Right-click menu: "Open Dashboard" (re-shows terminal) + "Quit" (identical to Ctrl+C) | `pystray.Menu` + `pystray.MenuItem`; Quit calls `icon.stop()` then triggers shutdown signal; Open Dashboard calls ShowWindow |
| TRAY-04 | Left-click toggles terminal window visible/minimized | Win32 backend calls `Icon.__call__()` on WM_LBUTTONUP → invokes `MenuItem(default=True)` action; action uses ctypes `GetConsoleWindow()` + `IsWindowVisible()` + `ShowWindow()` |
| TRAY-05 | No ghost icons after any exit path | `icon.stop()` posts WM_STOP → `_mainloop()` finally block calls `_hide()` (NIM_DELETE); `stop()` in `finally` block of cli/main.py covers all exit paths |

</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tray icon rendering (color, image) | OS / Native (win32) | ui/tray_manager.py | pystray win32 backend owns the NOTIFYICONDATA struct; TrayManager supplies the PIL Image |
| Utilization data read | WebPoller (thread-safe cache) | ui/tray_manager.py polls it | WebPoller.get_web_usage() already provides thread-safe Lock-protected reads |
| Tray lifecycle (start/stop) | cli/main.py | ui/tray_manager.py | cli/main.py owns all thread lifecycle; TrayManager encapsulates pystray details |
| Terminal window show/hide | OS / ctypes (user32/kernel32) | ui/tray_manager.py (calls ctypes) | GetConsoleWindow + ShowWindow is pure Windows API; no framework involved |
| Menu action "Quit" | cli/main.py (shutdown signal) | ui/tray_manager.py (triggers it) | Quit must be identical to Ctrl+C — must trigger the same shutdown path |
| Tooltip text | pystray (title property) | ui/tray_manager.py (updates it) | pystray maps Icon.title to NIF_TIP szTip field in win32 |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pystray | 0.19.5 | System tray icon + menu | Only maintained Python tray lib for Windows; win32 backend uses NOTIFYICONDATA natively |
| Pillow | 12.2.0 | Create PIL Image for tray icon | pystray requires a `PIL.Image.Image` instance; no alternative image format accepted |
| ctypes (stdlib) | stdlib | GetConsoleWindow, ShowWindow, IsWindowVisible | No extra dep; standard approach for Win32 API calls from Python |

[VERIFIED: npm view / pip index — pystray 0.19.5 is current as of 2026-05-19; Pillow 12.2.0 is current as of 2026-05-19]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| threading (stdlib) | stdlib | Lock for TrayManager shared state | If TrayManager needs to be accessed from the monitoring callback |
| signal (stdlib) | stdlib | Send SIGINT / raise KeyboardInterrupt for Quit | "Quit is identical to Ctrl+C" requires raising in the main thread |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pystray | infi.systray | infi.systray is Windows-only, less maintained, no Pillow image support |
| pystray | rumps | macOS-only; not applicable |
| Pillow ImageDraw | hand-crafted ICO bytes | Pillow is already a project dependency (will be); no reason to avoid it |

**Installation:**
```bash
pip install pystray>=0.19.5 Pillow>=12.0.0
```

**pyproject.toml additions:**
```toml
"pystray>=0.19.5",
"Pillow>=12.0.0",
```

---

## Architecture Patterns

### System Architecture Diagram

```
[WebPoller thread]
    └── get_web_usage() → WebUsageData (Lock-protected)
              │
              ▼
[TrayManager.update(utilization_pct, last_sync)]
    ├── _make_icon_image(color) → PIL Image
    │       └── icon.icon = new_image  ──→  [pystray win32 message loop thread]
    ├── icon.title = tooltip_str        ──→      NIM_MODIFY (NIF_ICON + NIF_TIP)
    └── (returns)

[pystray win32 message loop thread]  ← run_detached() spawns this
    ├── WM_LBUTTONUP → Icon.__call__() → default MenuItem action
    │       └── toggle_console_window() → ctypes ShowWindow/IsWindowVisible
    ├── WM_RBUTTONUP → TrackPopupMenuEx → user picks item
    │       ├── "Open Dashboard" → ShowWindow(SW_SHOW)
    │       └── "Quit" → icon.stop() + signal_shutdown()
    └── WM_STOP → _on_stop() → PostQuitMessage → _mainloop finally → _hide()

[Main thread — Rich Live loop]
    └── time.sleep(1) loop — unchanged
          │
          ▼ every monitoring cycle (10s)
    [on_data_update callback]
          └── calls tray_manager.update(web_usage) if tray_manager is not None
```

### Recommended Project Structure
```
ui/
├── tray_manager.py   # NEW: pystray wrapper + Pillow icon + ctypes window toggle
├── session_display.py
├── display_controller.py
└── ...
cli/
└── main.py           # MODIFIED: TrayManager init + start/stop lifecycle
```

### Pattern 1: TrayManager Class Structure

**What:** A self-contained class that owns pystray Icon lifecycle. Exposes `start()`, `stop()`, and `update(utilization_pct, last_sync_time)`.

**When to use:** Single instance created in `cli/main.py`, wired similarly to `WebPoller`.

```python
# Source: Derived from pystray official source + STATE.md architecture decision
import pystray
from PIL import Image, ImageDraw
import ctypes
import threading
from datetime import datetime
from typing import Optional

SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9

class TrayManager:
    def __init__(self, shutdown_callback):
        """
        shutdown_callback: callable that triggers clean shutdown (same as Ctrl+C).
        Called from the pystray message loop thread — must be thread-safe.
        """
        self._shutdown_callback = shutdown_callback
        self._icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Create pystray Icon, call run_detached(), set visible=True."""
        menu = pystray.Menu(
            pystray.MenuItem(
                "Toggle Dashboard",
                self._toggle_console,
                default=True,       # Left-click activates this item
                visible=False,      # Hidden from right-click menu (action is left-click)
            ),
            pystray.MenuItem("Open Dashboard", self._show_console),
            pystray.MenuItem("Quit", self._quit),
        )
        image = self._make_icon_image(0.0)  # initial green
        self._icon = pystray.Icon(
            "token-tracker",
            icon=image,
            title="Token Tracker — Utilization: --",
            menu=menu,
        )
        self._icon.run_detached()
        self._icon.visible = True

    def stop(self) -> None:
        """Stop the pystray icon cleanly. Safe to call if not started."""
        if self._icon is not None:
            self._icon.stop()

    def update(self, utilization_pct: Optional[float], last_sync: Optional[datetime]) -> None:
        """Update icon color and tooltip. Thread-safe — called from monitoring callback."""
        if self._icon is None:
            return
        with self._lock:
            self._icon.icon = self._make_icon_image(utilization_pct or 0.0)
            self._icon.title = self._build_tooltip(utilization_pct, last_sync)

    def _make_icon_image(self, utilization_pct: float) -> Image.Image:
        """Create a 64x64 solid color circle. Source: Pillow ImageDraw docs."""
        if utilization_pct < 50:
            color = (34, 197, 94)   # green
        elif utilization_pct < 75:
            color = (234, 179, 8)   # yellow
        else:
            color = (239, 68, 68)   # red
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=color)
        return img

    def _build_tooltip(self, utilization_pct: Optional[float], last_sync: Optional[datetime]) -> str:
        util_str = f"{utilization_pct:.1f}%" if utilization_pct is not None else "--"
        sync_str = last_sync.strftime("%H:%M:%S") if last_sync else "never"
        return f"Token Tracker  {util_str}  |  Last sync: {sync_str}"

    def _toggle_console(self, icon, item) -> None:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
            else:
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)

    def _show_console(self, icon, item) -> None:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)

    def _quit(self, icon, item) -> None:
        icon.stop()
        self._shutdown_callback()
```

### Pattern 2: Wiring in cli/main.py

**What:** TrayManager follows the same lifecycle as WebPoller — created after auth setup, started before monitoring loop, stopped in `finally`.

**When to use:** Always — this is the only integration point.

```python
# In _run_monitoring(), after web_poller setup and before orchestrator.start()
import os
import signal

def shutdown_signal():
    """Trigger clean shutdown from pystray thread (same as Ctrl+C)."""
    os.kill(os.getpid(), signal.CTRL_C_EVENT)  # Windows equivalent

tray_manager = TrayManager(shutdown_callback=shutdown_signal)
tray_manager.start()

# In on_data_update callback:
web_usage = monitoring_data.get("web_usage")
tray_manager.update(
    utilization_pct=web_usage.utilization_pct if web_usage else None,
    last_sync=monitoring_data.get("last_web_sync"),
)

# In finally block (alongside web_poller.stop()):
if "tray_manager" in locals() and tray_manager is not None:
    tray_manager.stop()
```

### Pattern 3: Pillow Circle Icon Creation

**What:** Create a transparent-background 64x64 PIL Image with a filled ellipse. pystray accepts RGBA images on Windows.

**Source:** [VERIFIED: Context7 /python-pillow/pillow — ImageDraw.ellipse docs]

```python
from PIL import Image, ImageDraw

def make_circle_icon(color_rgb: tuple, size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color_rgb
    )
    return img
```

### Anti-Patterns to Avoid

- **Using `icon.run()` instead of `icon.run_detached()`:** `run()` on Windows blocks the calling thread. Since the main thread runs the Rich Live display loop, calling `run()` from main would hang the display. STATE.md locks this as `run_detached()`. [VERIFIED: pystray source — `_run_detached()` spawns its own thread on win32]
- **Calling `run_detached()` from a daemon thread:** `run_detached()` starts an internal thread. If called from a daemon thread that dies early, the internal thread may terminate unexpectedly. Call from the main thread after `live_display.__enter__()`.
- **Updating `icon.icon` or `icon.title` without the icon being visible:** Source shows `_update_icon()` is only called when `self.visible` is True. Set `icon.visible = True` before updating. In `TrayManager.start()`, call `run_detached()` first, then `icon.visible = True`.
- **Using `os.kill(pid, signal.SIGINT)` for Quit on Windows:** `signal.SIGINT` is not reliable on Windows for cross-thread shutdown. Use `os.kill(os.getpid(), signal.CTRL_C_EVENT)` which raises `KeyboardInterrupt` in the main thread — the same signal path as Ctrl+C. [ASSUMED — verify behavior at runtime]
- **Calling `icon.stop()` from within a MenuItem action without also signaling shutdown:** `icon.stop()` only stops the tray. The main process (Rich Live loop) must also be told to exit. The Quit action must both call `icon.stop()` AND trigger the shutdown signal.
- **Setting `visible=False` on the default MenuItem instead of hiding it:** The default MenuItem handles left-click. It must not appear in the right-click menu as a duplicate of "Open Dashboard". Use `visible=False` on the `default=True` MenuItem to hide it from the popup while keeping left-click wired.
- **Using a mutable Menu (calling `update_menu()`) on every polling cycle:** Menu construction is expensive on Windows (creates HMENU resources). Menu items with static actions do not need `update_menu()`. Only call it if menu item text or enabled state changes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| System tray icon | Win32 NOTIFYICONDATA wrapper | pystray | NOTIFYICONDATA + Shell_NotifyIcon + WM_NOTIFY + message pump is 300+ lines of ctypes; pystray wraps it correctly |
| Tray icon image | ICO file format byte-crafting | Pillow Image | pystray accepts PIL Image; ICO format byte manipulation is error-prone |
| Thread-safe icon update | Custom lock + PostMessage | pystray icon.icon = setter | pystray setter calls `_update_icon()` if visible; thread-safe by design for property assignment |
| Console HWND lookup | Window title search (FindWindow) | `kernel32.GetConsoleWindow()` | GetConsoleWindow() is the correct API for the current process's console; FindWindow by title is fragile |

**Key insight:** pystray + Pillow covers 95% of the complexity. The only hand-rolled piece is `ctypes GetConsoleWindow/ShowWindow` for the terminal toggle, which is a 5-line function.

---

## Common Pitfalls

### Pitfall 1: run_detached() Does Not Set visible=True

**What goes wrong:** After calling `icon.run_detached()`, the icon is NOT visible. The setup callback (if none provided) sets `visible=True`, but only after the internal thread marks ready. The default setup callback fires in a thread; if you check `icon.visible` immediately after `run_detached()`, it may be False.

**Why it happens:** `run_detached()` calls `_start_setup(setup)` which starts a thread that waits on `__queue.get()`. The queue item is added when `_mark_ready()` is called from within `_run()`. There is a race between the thread starting and `_mark_ready()` being called.

**How to avoid:** After `icon.run_detached()`, explicitly set `icon.visible = True` after a brief wait, or pass a custom setup that sets `visible = True`:
```python
self._icon.run_detached(setup=lambda icon: setattr(icon, 'visible', True))
```
Or simply: `icon.run_detached()` then `icon.visible = True` (the setter queues via `_show()` which is safe).

**Warning signs:** Tray icon never appears; no error raised.

### Pitfall 2: Quit Action Must Signal Main Thread, Not Just Stop the Icon

**What goes wrong:** `_quit` calls only `icon.stop()`. The pystray loop exits, the icon disappears, but the main thread's `while True: time.sleep(1)` loop (or `signal.pause()` fallback) keeps running. Process hangs.

**Why it happens:** `icon.stop()` only terminates the win32 message loop. It has no connection to the main process loop.

**How to avoid:** After `icon.stop()`, trigger the same shutdown path as Ctrl+C:
```python
def _quit(self, icon, item):
    icon.stop()
    os.kill(os.getpid(), signal.CTRL_C_EVENT)  # raises KeyboardInterrupt in main thread
```
The existing `except KeyboardInterrupt` handler in `cli/main.py` then calls `handle_cleanup_and_exit()`.

**Warning signs:** Icon disappears but process keeps running; requires manual Ctrl+C.

### Pitfall 3: signal.CTRL_C_EVENT vs signal.SIGINT on Windows

**What goes wrong:** `os.kill(pid, signal.SIGINT)` on Windows raises `OSError` (not valid on Win32 for SIGINT). The process does not shut down.

**Why it happens:** Windows does not implement POSIX signals the same way. `signal.SIGINT` = 2 but `os.kill` on Windows only supports `signal.SIGTERM` (15) and `signal.CTRL_C_EVENT` (0) and `signal.CTRL_BREAK_EVENT` (1).

**How to avoid:** Use `os.kill(os.getpid(), signal.CTRL_C_EVENT)`. This sends Ctrl+C to the process group and raises `KeyboardInterrupt` in the main thread.

**Warning signs:** `OSError: [WinError 87]` when calling `os.kill` from the Quit menu item.

### Pitfall 4: icon.icon Setter Silently No-Ops When Icon Not Visible

**What goes wrong:** Color update is called before the icon is visible (e.g., first WebPoller result arrives before `run_detached()` has finished marking ready). The new image is stored in `_icon` but `_update_icon()` is NOT called. The icon appears with the initial color indefinitely.

**Why it happens:** From source: `if value: if self.visible: self._update_icon()` — the update only fires if visible is True.

**How to avoid:** `TrayManager.update()` should guard on `self._icon is not None and self._icon.visible` before setting, or rely on the fact that `start()` sets `visible=True` early and subsequent updates will work.

**Warning signs:** Tray icon stays green even after utilization exceeds 50%; icon image never changes.

### Pitfall 5: Ghost Icon When stop() Is NOT Called (Process Crash)

**What goes wrong:** If the process terminates without calling `icon.stop()`, the win32 message loop thread terminates abruptly. `_mainloop()` finally block calls `_hide()` (NIM_DELETE), but only if the thread reaches the finally. A hard kill (SIGKILL, task manager) bypasses this.

**Why it happens:** Ghost icons in the notification area are cached by Windows Shell. They clear when hovered over.

**How to avoid:** This is unavoidable for hard kills. For all expected exit paths (Ctrl+C, Quit menu, exception in main), ensure `tray_manager.stop()` is in the `finally` block of `_run_monitoring()`. The pystray `__del__` method also calls `_hide()` if visible — this handles garbage collection on clean exits.

**Warning signs:** Ghost icon visible in notification area after app exit; disappears on hover.

### Pitfall 6: Left-Click Default MenuItem Must Be default=True

**What goes wrong:** Left-click on the tray icon does nothing (no toggle).

**Why it happens:** On Windows, `WM_LBUTTONUP` calls `Icon.__call__()` → `Menu.__call__()` → `next(item for item in menu.items if item.default)(icon)`. If no MenuItem has `default=True`, `StopIteration` is caught and nothing happens.

**How to avoid:** The console toggle MenuItem must have `default=True`:
```python
pystray.MenuItem("Toggle Dashboard", self._toggle_console, default=True, visible=False)
```
`visible=False` hides it from the right-click popup; `default=True` wires the left-click.

**Warning signs:** Left-clicking the tray icon has no effect.

### Pitfall 7: run_detached() on Windows Is Not Main-Thread-Required

**What goes wrong:** Developer sees "must be called from main thread" in docs and worries about calling `run_detached()` from inside the Rich Live context (which IS the main thread).

**Why it happens:** The "must be called from main thread" restriction is macOS-only. The pystray docs say: "If you only target Windows, calling run() from a non-main thread is safe."

**How to avoid:** On Windows, `run_detached()` can safely be called from any thread, including the main thread inside the Rich Live `with` block. Call it after `live_display.__enter__()` without concern.

**Warning signs:** N/A — this is NOT a real pitfall on Windows. Document it to prevent over-engineering a workaround.

---

## Code Examples

### Full pystray Icon Lifecycle (Verified)
```python
# Source: [VERIFIED: pystray 0.19.5 source /_base.py + /_win32.py]
import pystray
from PIL import Image, ImageDraw

# Create image
img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
ImageDraw.Draw(img).ellipse([4, 4, 60, 60], fill=(34, 197, 94))  # green circle

# Create icon with menu
icon = pystray.Icon(
    "my-app",
    icon=img,
    title="My App — 42%",
    menu=pystray.Menu(
        pystray.MenuItem("Toggle", on_toggle, default=True, visible=False),
        pystray.MenuItem("Open Dashboard", on_open),
        pystray.MenuItem("Quit", on_quit),
    )
)

# Start detached (spawns internal thread on win32)
icon.run_detached()
icon.visible = True

# Update while running (thread-safe property setters)
icon.icon = new_image          # calls _update_icon() if visible
icon.title = "My App — 67%"   # calls _update_title() if visible

# Clean stop (posts WM_STOP → _mainloop finally → _hide/NIM_DELETE)
icon.stop()
```

### Console Window Toggle
```python
# Source: [VERIFIED: Windows API via WebSearch + ctypes stdlib]
import ctypes
import signal
import os

SW_HIDE    = 0
SW_RESTORE = 9

def toggle_console_window() -> None:
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if not hwnd:
        return
    if ctypes.windll.user32.IsWindowVisible(hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
    else:
        ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)

def show_console_window() -> None:
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)

def trigger_quit() -> None:
    """Send Ctrl+C to own process — raises KeyboardInterrupt in main thread."""
    os.kill(os.getpid(), signal.CTRL_C_EVENT)
```

### Pillow Color Circle
```python
# Source: [VERIFIED: Context7 /python-pillow/pillow — ImageDraw.ellipse]
from PIL import Image, ImageDraw
from typing import Tuple

def make_circle_icon(color: Tuple[int, int, int], size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    margin = size // 16  # 4px at 64px size
    ImageDraw.Draw(img).ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color
    )
    return img

GREEN  = (34, 197, 94)   # <50% utilization
YELLOW = (234, 179, 8)   # 50-75%
RED    = (239, 68, 68)   # >75%

def utilization_to_color(pct: float) -> Tuple[int, int, int]:
    if pct < 50:
        return GREEN
    elif pct < 75:
        return YELLOW
    return RED
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `icon.run()` in separate thread | `icon.run_detached()` | pystray 0.14+ | run_detached is the designed integration path; run() in a thread still works on Windows but is semantically wrong |
| infi.systray (Windows-only) | pystray (cross-platform) | ~2020 | pystray is actively maintained; infi.systray is not |
| PIL (abandoned) | Pillow | 2010+ | Pillow is the maintained fork; same import path `from PIL import ...` |

**Deprecated/outdated:**
- `icon.run()` from a daemon thread: technically works on Windows but creates a race condition with cleanup; `run_detached()` is the supported integration pattern
- `pystray` versions <0.14: lacked `run_detached()`; do not target those versions

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `os.kill(os.getpid(), signal.CTRL_C_EVENT)` raises `KeyboardInterrupt` in the main thread on Windows when called from a non-main thread | Common Pitfalls / Pattern 2 | If wrong, Quit menu item stops the tray but does not shut down the process; need alternative such as `threading.main_thread().raise_exception()` or a `threading.Event` shutdown flag |
| A2 | `icon.visible = True` immediately after `icon.run_detached()` is race-condition-free | Pitfall 1 / Pattern 1 | If wrong, visible setter may fire before `_hwnd` is created; need `setup` callback instead |
| A3 | Setting `icon.icon` from the monitoring callback thread (not the pystray message loop thread) is thread-safe | Pattern 1 | pystray property setter calls `_update_icon()` which calls `self._message()` which posts to the win32 message queue — this is thread-safe by Windows message queue design; low risk but [ASSUMED] that pystray does not hold a non-reentrant lock |

---

## Open Questions

1. **CTRL_C_EVENT behavior from pystray thread**
   - What we know: `os.kill(os.getpid(), signal.CTRL_C_EVENT)` is the Windows equivalent of Ctrl+C; documented in Python stdlib
   - What's unclear: Whether calling it from the pystray message loop thread (not the main thread) correctly raises `KeyboardInterrupt` in the main thread vs. the calling thread
   - Recommendation: Test this in Plan 05-01 with a smoke test. Fallback: use a `threading.Event` shutdown flag polled by the main loop instead of signal delivery

2. **visible=True race after run_detached()**
   - What we know: `_run_detached()` spawns a thread; `_mark_ready()` is called from within that thread; the setup callback fires after `_mark_ready()`
   - What's unclear: Whether calling `icon.visible = True` immediately after `run_detached()` in the main thread ever executes before `_hwnd` is initialized
   - Recommendation: Use `setup` callback to set visible: `icon.run_detached(setup=lambda icon: setattr(icon, 'visible', True))`. This guarantees visibility is set only after the message loop is ready.

3. **Tooltip length limit on Windows**
   - What we know: `szTip` in NOTIFYICONDATA is a fixed 128-character buffer (WCHAR[128])
   - What's unclear: How pystray handles truncation; whether the tooltip silently truncates or raises
   - Recommendation: Keep tooltip under 100 characters. Format: `"Token Tracker  67.3%  |  Last sync: 14:32:07"` is ~45 chars — well within limit.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pystray | TRAY-01 through TRAY-05 | Not yet installed | Latest: 0.19.5 | None — no alternative |
| Pillow | TRAY-01 (icon image) | Not yet installed | Latest: 12.2.0 | None — pystray requires PIL.Image |
| ctypes | TRAY-04 (window toggle) | stdlib (always present) | stdlib | None needed |
| signal | TRAY-03 (Quit) | stdlib (always present) | stdlib | None needed |
| Python 3.11+ | All | Confirmed (pyproject.toml requires >=3.11) | 3.11+ | — |

**Missing dependencies with no fallback:**
- `pystray>=0.19.5` — must be added to `pyproject.toml` dependencies and installed
- `Pillow>=12.0.0` — must be added to `pyproject.toml` dependencies and installed

**Wave 0 task:** Add both to pyproject.toml and `pip install -e ".[dev]"` to reinstall.

---

## Sources

### Primary (HIGH confidence)
- `/tmp/pystray_src/pystray/_base.py` (pystray 0.19.5 wheel extracted) — `run_detached`, `stop`, `Icon.title`, `Icon.icon` setter, `Menu.__call__` default-item invocation, `Icon.__del__` cleanup
- `/tmp/pystray_src/pystray/_win32.py` (pystray 0.19.5 wheel extracted) — `_run_detached()` spawns thread, `_stop()` posts WM_STOP, `_mainloop()` finally calls `_hide()`, `WM_LBUTTONUP` → `Icon.__call__()`, `_update_title()` uses NIF_TIP
- Context7 `/python-pillow/pillow` — `ImageDraw.ellipse`, `Image.new("RGBA", ...)`, confirmed code patterns
- `pip index versions pystray` — confirmed 0.19.5 is current [VERIFIED: PyPI registry 2026-05-19]
- `pip index versions Pillow` — confirmed 12.2.0 is current [VERIFIED: PyPI registry 2026-05-19]
- `pystray.readthedocs.io/en/latest/reference.html` — `Icon.__init__` params, `title` as tooltip param

### Secondary (MEDIUM confidence)
- WebSearch: Windows `ctypes.windll.kernel32.GetConsoleWindow()` + `ctypes.windll.user32.ShowWindow()` / `IsWindowVisible()` — confirmed as standard pattern from multiple sources; SW_HIDE=0, SW_RESTORE=9, SW_SHOW=5 constants confirmed
- pystray GitHub issue #74 — ghost icon behavior: ghost only occurs with hard kills or hidden-section dragging; `stop()` → `_hide()` (NIM_DELETE) is sufficient for normal exits
- pystray GitHub issue #94 — `stop()` on Windows: WM_STOP posts quit message cleanly; thread terminates normally

### Tertiary (LOW confidence)
- A1 (CTRL_C_EVENT cross-thread) — assumed based on Python docs but not tested in this environment

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed via pip registry; pystray source inspected directly
- Architecture: HIGH — pystray win32 backend source read directly; no guessing about API
- Pitfalls: HIGH (technical mechanisms) / MEDIUM (A1 shutdown signal) — most derived from source code inspection
- ctypes window toggle: HIGH — standard Windows API, confirmed across multiple sources

**Research date:** 2026-05-19
**Valid until:** 2026-11-19 (pystray 0.19.x is stable; API unlikely to change; 6-month shelf life)
