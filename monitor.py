#!/usr/bin/env python3
"""Root-level entry point for the Claude Token Tracker.

Windows UTF-8 reconfiguration is performed before any Rich or upstream imports
so that box-drawing characters and emoji render correctly regardless of the
active console code page.

Usage:
    python monitor.py [options]
    python monitor.py --help
"""

# Windows UTF-8 + VT reconfiguration — MUST come before any Rich imports.
import os
import sys

if sys.platform == "win32":
    import ctypes as _ctypes
    _k32 = _ctypes.windll.kernel32  # type: ignore[attr-defined]
    if os.environ.get("_TOKEN_TRACKER_DETACHED"):
        # Running in a detached classic conhost.exe window.  Use the native
        # UTF-8 code page (CP 65001) so Rich sees a real TTY and renders
        # colours/box-drawing correctly.  TextIOWrapper wrapping breaks
        # Rich's isatty() detection in conhost.
        _k32.SetConsoleOutputCP(65001)
        _k32.SetConsoleCP(65001)
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        # Must be called before the shell registers our window — sets a unique
        # AppUserModelID so the taskbar button uses our icon instead of python.exe's.
        try:
            _ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "TokenTracker.Console.1"
            )
        except Exception:
            pass
    else:
        # Running inside Windows Terminal (ConPTY) or an initial shell session.
        # Wrap stdout/stderr with a UTF-8 TextIOWrapper for correct encoding.
        import io as _io
        sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING for ANSI colour codes.
    # Read-modify-write preserves other mode bits instead of clobbering them.
    # restype=c_void_p avoids 32-bit truncation of the 64-bit HANDLE on x64.
    _ENABLE_VT = 0x0004
    try:
        _k32.GetStdHandle.restype = _ctypes.c_void_p
        _h = _k32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if _h:  # None = NULL handle; skip silently
            _mode = _ctypes.c_ulong(0)
            if _k32.GetConsoleMode(_h, _ctypes.byref(_mode)):
                _k32.SetConsoleMode(_h, _mode.value | _ENABLE_VT)
    except Exception:
        pass

# Ensure the repo root is on sys.path before importing flat modules.
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Import the upstream CLI main function via the flat module layout.
# The upstream entry point is cli/main.py::main().
from cli.main import main as _upstream_main  # noqa: E402


def main() -> int:
    """Delegate to the upstream CLI main function.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    result = _upstream_main()
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
