"""System tray icon manager for Token Tracker.

Wraps pystray Icon lifecycle. Exposes start(), stop(), update().
Threading model (per STATE.md):
  - Tray: icon.run_detached() called from main thread — NOT a 4th thread
  - update() called from MonitoringThread via on_data_update callback
  - icon.stop() called from main thread finally block in cli/main.py
"""
import ctypes
import io
import logging
import os
import signal
import tempfile
import threading
from datetime import datetime
from typing import Callable, Optional, Tuple


import pystray
from PIL import Image

logger = logging.getLogger(__name__)

# Windows ShowWindow / GetAncestor / extended-style constants
SW_HIDE = 0
SW_RESTORE = 9
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000   # forces taskbar button — must be cleared to hide
WS_EX_TOOLWINDOW = 0x00000080  # omits window from taskbar/Alt-Tab

# SetConsoleCtrlHandler constants
CTRL_CLOSE_EVENT = 2  # fired when the user clicks the console's X button

# Callback type for SetConsoleCtrlHandler: BOOL WINAPI HandlerRoutine(DWORD dwCtrlType)
_HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)

# Utilization color thresholds
_COLOR_LIGHT_GREEN = (134, 239, 172)  # <25%
_COLOR_GREEN       = (34,  197, 94)   # 25–50%
_COLOR_YELLOW      = (234, 179, 8)    # 50–75%
_COLOR_ORANGE      = (249, 115, 22)   # 75–90%
_COLOR_RED         = (239, 68,  68)   # >=90%

# 8-bit coin pixel art — 16×16 logical pixels, rendered at 4× scale (64×64 output).
# T=transparent, O=dark outline, H=highlight, M=main fill, S=shadow
_T, _O, _H, _M, _S = 0, 1, 2, 3, 4
_COIN = [
    #  0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15
    [_T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T],  # 0
    [_T, _T, _T, _T, _T, _O, _O, _O, _O, _O, _T, _T, _T, _T, _T, _T],  # 1
    [_T, _T, _T, _O, _O, _H, _H, _M, _M, _M, _O, _O, _T, _T, _T, _T],  # 2
    [_T, _T, _O, _H, _H, _H, _M, _M, _M, _M, _M, _M, _O, _T, _T, _T],  # 3
    [_T, _O, _M, _H, _H, _M, _M, _M, _M, _M, _M, _M, _M, _O, _T, _T],  # 4
    [_T, _O, _M, _H, _M, _M, _M, _M, _M, _M, _M, _M, _M, _O, _T, _T],  # 5
    [_O, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _O, _T],  # 6
    [_O, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _O, _T],  # 7
    [_O, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _O, _T],  # 8
    [_O, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _S, _O, _T],  # 9
    [_T, _O, _M, _M, _M, _M, _M, _M, _M, _M, _M, _M, _S, _O, _T, _T],  # 10
    [_T, _O, _M, _M, _M, _M, _M, _M, _M, _M, _M, _S, _S, _O, _T, _T],  # 11
    [_T, _T, _O, _M, _M, _M, _M, _M, _M, _M, _S, _S, _O, _T, _T, _T],  # 12
    [_T, _T, _T, _T, _O, _M, _M, _M, _M, _M, _O, _T, _T, _T, _T, _T],  # 13
    [_T, _T, _T, _T, _T, _O, _O, _O, _O, _O, _T, _T, _T, _T, _T, _T],  # 14
    [_T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T],  # 15
]


def _set_console_window_icon(image: Image.Image) -> None:
    """Set the Win32 console window's title-bar AND taskbar icon from a PIL Image.

    Three-step approach for Windows 10/11:
      1. SetCurrentProcessExplicitAppUserModelID — gives the process its own
         taskbar group so Windows stops inheriting python.exe's icon.
      2. WM_SETICON (ICON_BIG / ICON_SMALL) — per-window icon slots.
      3. SetClassLongPtrW (GCLP_HICON / GCLP_HICONSM) — updates the window
         class icon that the shell reads for the taskbar button.

    No-ops silently when there is no Win32 console window (e.g. ConPTY).
    """
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return

        # Step 1: own AppUserModelID so the taskbar doesn't use python.exe's icon
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "TokenTracker.Console.1"
            )
        except Exception:
            pass

        # Build ICO with multiple sizes for crisp rendering at every DPI
        buf = io.BytesIO()
        image.save(buf, format="ICO", sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])

        fd, tmp_path = tempfile.mkstemp(suffix=".ico")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(buf.getvalue())

            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            LR_DEFAULTSIZE  = 0x00000040

            hicon_big = ctypes.windll.user32.LoadImageW(
                None, tmp_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
            hicon_small = ctypes.windll.user32.LoadImageW(
                None, tmp_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        WM_SETICON   = 0x0080
        GCLP_HICON   = -14   # class large icon
        GCLP_HICONSM = -34   # class small icon

        # Step 2: per-window icon
        if hicon_big:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_big)
        if hicon_small:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_small)

        # Step 3: window-class icon (what the shell taskbar reads)
        if hicon_big:
            ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICON, hicon_big)
        if hicon_small:
            ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, hicon_small)

    except Exception:
        pass


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
        self._stopped = False
        self._saved_exstyle: Optional[int] = None  # original exstyle before hide
        self._ctrl_handler_cb = None  # prevents GC of SetConsoleCtrlHandler callback
        self._console_hidden: bool = False  # set by _do_hide/_do_show; avoids polling IsWindowVisible
        self._on_restore: Optional[Callable[[], None]] = None

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
                visible=False,  # hidden from right-click menu — left-click only
            ),
            pystray.MenuItem("Hide to Tray", self._hide_console),
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
        _set_console_window_icon(image)  # match taskbar icon to tray coin
        # setup callback fires after message loop is ready — safe visible=True
        self._icon.run_detached(setup=lambda icon: setattr(icon, "visible", True))
        logger.info("TrayManager: icon started (run_detached)")

    def stop(self) -> None:
        """Stop the pystray icon cleanly. Safe to call if not started or already stopped.

        Idempotent: a second call (e.g. from _quit() then finally block) is a no-op.
        """
        if self._icon is not None and not self._stopped:
            self._stopped = True
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
        """Create a 64x64 RGBA PIL Image: an 8-bit coin, color-coded by utilization.

        The coin is defined as a 16×16 pixel-art grid (_COIN) scaled 4× to 64×64.
        Highlight and shadow are derived from the main utilization color.
        """
        r, g, b = _utilization_to_color(utilization_pct)

        def _c(v: float) -> int:
            return max(0, min(255, int(v)))

        color_map = {
            _T: (0, 0, 0, 0),
            _O: (_c(r * 0.35), _c(g * 0.35), _c(b * 0.35), 255),
            _M: (r, g, b, 255),
            _H: (_c(r * 1.5 + 20), _c(g * 1.5 + 20), _c(b * 1.5 + 20), 255),
            _S: (_c(r * 0.50), _c(g * 0.50), _c(b * 0.50), 255),
        }

        SCALE = 4
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        pixels = img.load()
        for row_i, row in enumerate(_COIN):
            for col_i, cell in enumerate(row):
                rgba = color_map[cell]
                for dy in range(SCALE):
                    for dx in range(SCALE):
                        pixels[col_i * SCALE + dx, row_i * SCALE + dy] = rgba
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
        sync_str = last_sync.astimezone().strftime("%H:%M:%S") if last_sync is not None else "never"
        return f"Token Tracker  {util_str}  |  Last sync: {sync_str}"

    def set_restore_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked immediately after the console window is shown.

        Used to reset the terminal cursor position so Rich's cursor-tracking
        stays correct after the window was hidden (log output written while
        hidden shifts the cursor, causing the next render to land in the wrong spot).
        """
        self._on_restore = callback

    def is_console_visible(self) -> bool:
        """Return True when the console window is visible to the user.

        Reads a flag set by _do_hide/_do_show rather than calling IsWindowVisible
        on every monitoring cycle — Win32 polls are unreliable in Windows Terminal
        (the call can return False intermittently, causing display flicker).
        """
        return not self._console_hidden

    @staticmethod
    def _top_hwnd() -> int:
        """Return the top-level window HWND for the console.

        GetConsoleWindow() may return a child/embedded window inside Windows
        Terminal. GetAncestor(GA_ROOT) walks to the outermost ancestor so that
        ShowWindow(SW_HIDE) removes the entry from the taskbar entirely rather
        than just collapsing a pane.
        """
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return 0
        root = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
        return root if root else hwnd

    def _install_close_guard(self) -> None:
        """Register a SetConsoleCtrlHandler callback that hides on CTRL_CLOSE_EVENT.

        Guard logic:
          - No console window (hwnd=0): skip silently.
          - Console shared with a parent shell (GetConsoleProcessList > 1): skip,
            log INFO — the X button should close the shell normally in that case.
          - Sole owner (count==1): install the handler and store the callback in
            self._ctrl_handler_cb to prevent CPython from GC-ing the ctypes object.
        """
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            logger.info("TrayManager: no console window — close guard skipped")
            return

        buf = (ctypes.c_ulong * 2)()
        count = ctypes.windll.kernel32.GetConsoleProcessList(buf, 2)
        if count != 1:
            logger.info(
                "TrayManager: console shared (count=%d) — close guard skipped", count
            )
            return

        def _handler(event: int) -> bool:
            if event == CTRL_CLOSE_EVENT:
                ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
                return True
            return False

        self._ctrl_handler_cb = _HandlerRoutine(_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(self._ctrl_handler_cb, True)
        logger.info("TrayManager: CTRL_CLOSE_EVENT guard installed")

    def _toggle_console(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Toggle terminal window visible/hidden (left-click tray action)."""
        hwnd = self._top_hwnd()
        if not hwnd:
            return
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            self._do_hide(hwnd)
        else:
            self._do_show(hwnd)

    def _hide_console(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Hide the terminal window to the tray (right-click menu action)."""
        hwnd = self._top_hwnd()
        if hwnd:
            self._do_hide(hwnd)

    def _show_console(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Show/restore the terminal window (right-click Open Dashboard)."""
        hwnd = self._top_hwnd()
        if hwnd:
            self._do_show(hwnd)

    def _do_hide(self, hwnd: int) -> None:
        """Remove window from taskbar and hide it."""
        exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        self._saved_exstyle = exstyle
        new_style = (exstyle & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
        self._console_hidden = True

    def _do_show(self, hwnd: int) -> None:
        """Restore window to taskbar and bring it to front."""
        if self._saved_exstyle is not None:
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, self._saved_exstyle)
            self._saved_exstyle = None
        ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        self._console_hidden = False
        if self._on_restore is not None:
            self._on_restore()

    def _quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Trigger clean shutdown identical to Ctrl+C (TRAY-03 Quit).

        Per RESEARCH.md Pitfall 2-3:
          1. icon.stop() first — removes tray icon (NIM_DELETE via WM_STOP)
          2. os.kill(pid, CTRL_C_EVENT) — raises KeyboardInterrupt in main thread
             (CTRL_C_EVENT not SIGINT — SIGINT raises OSError on Windows)
        Fallback: if CTRL_C_EVENT raises OSError, calls shutdown_callback directly.
        """
        icon.stop()
        self._shutdown_callback()


def _utilization_to_color(pct: float) -> Tuple[int, int, int]:
    """Map utilization percentage to RGB color tuple.

      <25%:   light green (134, 239, 172)
      25–50%: green       (34,  197, 94)
      50–75%: yellow      (234, 179, 8)
      75–90%: orange      (249, 115, 22)
      >=90%:  red         (239, 68,  68)
    """
    if pct < 25:
        return _COLOR_LIGHT_GREEN
    if pct < 50:
        return _COLOR_GREEN
    if pct < 75:
        return _COLOR_YELLOW
    if pct < 90:
        return _COLOR_ORANGE
    return _COLOR_RED
