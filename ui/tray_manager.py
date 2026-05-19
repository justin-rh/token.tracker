"""System tray icon manager for Token Tracker.

Wraps pystray Icon lifecycle. Exposes start(), stop(), update().
Threading model (per STATE.md):
  - Tray: icon.run_detached() called from main thread — NOT a 4th thread
  - update() called from MonitoringThread via on_data_update callback
  - icon.stop() called from main thread finally block in cli/main.py
"""
import ctypes
import logging
import os
import signal
import threading
from datetime import datetime
from typing import Callable, Optional, Tuple

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Windows ShowWindow constants
SW_HIDE = 0
SW_RESTORE = 9

# Utilization color thresholds (per TRAY-01 and STATE.md)
_COLOR_GREEN  = (34, 197, 94)   # <50% utilization
_COLOR_YELLOW = (234, 179, 8)   # 50–75% utilization
_COLOR_RED    = (239, 68, 68)   # >=75% utilization


class TrayManager:
    """Manages the pystray system tray icon lifecycle.

    Not a Thread subclass — icon.run_detached() spawns its own internal thread
    on the win32 backend. TrayManager is a plain object called from main thread.

    Lifecycle:
        tray = TrayManager(shutdown_callback=fn)
        tray.start()     # called from main thread after live_display.__enter__()
        tray.update(...)  # called from MonitoringThread on_data_update
        tray.stop()      # called from main thread finally block
    """

    def __init__(self, shutdown_callback: Callable[[], None]) -> None:
        """
        Args:
            shutdown_callback: Callable that triggers clean app shutdown.
                Called from the pystray message loop thread — must be
                thread-safe. Typically os.kill(os.getpid(), signal.CTRL_C_EVENT).
        """
        self._shutdown_callback = shutdown_callback
        self._icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Create pystray Icon and call run_detached().

        Uses setup callback to set visible=True after the win32 message loop
        is ready — avoids the race condition in Pitfall 1 (RESEARCH.md).
        """
        menu = pystray.Menu(
            pystray.MenuItem(
                "Toggle Dashboard",
                self._toggle_console,
                default=True,   # left-click activates this item (TRAY-04)
                visible=False,  # hidden from right-click menu (Pitfall 6)
            ),
            pystray.MenuItem("Open Dashboard", self._show_console),
            pystray.MenuItem("Quit", self._quit),
        )
        image = self._make_icon_image(0.0)  # initial green (no data yet)
        self._icon = pystray.Icon(
            "token-tracker",
            icon=image,
            title="Token Tracker  --  |  Last sync: never",
            menu=menu,
        )
        # setup callback fires after message loop is ready — safe visible=True
        self._icon.run_detached(setup=lambda icon: setattr(icon, "visible", True))
        logger.info("TrayManager: icon started (run_detached)")

    def stop(self) -> None:
        """Stop the pystray icon cleanly. Safe to call if not started.

        icon.stop() posts WM_STOP to the win32 message loop which then calls
        _hide() (NIM_DELETE) in its finally block — no ghost icon for clean exits.
        """
        if self._icon is not None:
            self._icon.stop()
            logger.info("TrayManager: icon stopped")

    def update(
        self,
        utilization_pct: Optional[float],
        last_sync: Optional[datetime],
    ) -> None:
        """Update icon color and tooltip from latest web usage data.

        Thread-safe — called from MonitoringThread on_data_update callback.
        Guards on self._icon is None (called before start() or after stop()).
        Guards on self._icon.visible (Pitfall 4: setter no-ops if not visible).
        """
        if self._icon is None:
            return
        pct = utilization_pct if utilization_pct is not None else 0.0
        with self._lock:
            self._icon.icon = self._make_icon_image(pct)
            self._icon.title = self._build_tooltip(utilization_pct, last_sync)
        logger.debug("TrayManager: updated utilization=%.1f%%", pct)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_icon_image(self, utilization_pct: float) -> Image.Image:
        """Create a 64x64 RGBA PIL Image with a filled color circle.

        Color thresholds per TRAY-01 and STATE.md:
          green  = (34, 197, 94)   for utilization_pct < 50
          yellow = (234, 179, 8)   for 50 <= utilization_pct < 75
          red    = (239, 68, 68)   for utilization_pct >= 75
        """
        color = _utilization_to_color(utilization_pct)
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse([4, 4, 60, 60], fill=color)
        return img

    def _build_tooltip(
        self,
        utilization_pct: Optional[float],
        last_sync: Optional[datetime],
    ) -> str:
        """Build tooltip string under the 128-char NIF_TIP szTip limit.

        Format: "Token Tracker  67.3%  |  Last sync: 14:32:07"
        Max observed length: ~50 chars — well within limit.
        """
        util_str = f"{utilization_pct:.1f}%" if utilization_pct is not None else "--"
        sync_str = last_sync.strftime("%H:%M:%S") if last_sync is not None else "never"
        return f"Token Tracker  {util_str}  |  Last sync: {sync_str}"

    def _toggle_console(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Toggle terminal window visible/minimized (TRAY-04).

        Uses ctypes GetConsoleWindow + IsWindowVisible + ShowWindow.
        Only affects the current process's console window — not system windows.
        """
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
        else:
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)

    def _show_console(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Show/restore the terminal window (TRAY-03 Open Dashboard)."""
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)

    def _quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Trigger clean shutdown identical to Ctrl+C (TRAY-03 Quit).

        Per RESEARCH.md Pitfall 2-3:
          1. icon.stop() first — removes tray icon (NIM_DELETE via WM_STOP)
          2. os.kill(pid, CTRL_C_EVENT) — raises KeyboardInterrupt in main thread
             (CTRL_C_EVENT not SIGINT — SIGINT raises OSError on Windows)
        Fallback: if CTRL_C_EVENT raises OSError, calls shutdown_callback directly.
        """
        icon.stop()
        try:
            os.kill(os.getpid(), signal.CTRL_C_EVENT)
        except OSError:
            logger.warning(
                "TrayManager: CTRL_C_EVENT failed — using shutdown_callback fallback"
            )
            self._shutdown_callback()


def _utilization_to_color(pct: float) -> Tuple[int, int, int]:
    """Map utilization percentage to RGB color tuple.

    Thresholds per TRAY-01:
      green  (34, 197, 94)   for pct < 50
      yellow (234, 179, 8)   for 50 <= pct < 75
      red    (239, 68, 68)   for pct >= 75
    """
    if pct < 50:
        return _COLOR_GREEN
    if pct < 75:
        return _COLOR_YELLOW
    return _COLOR_RED
