#!/usr/bin/env python3
"""Root-level entry point for the Claude Token Tracker.

Windows UTF-8 reconfiguration is performed before any Rich or upstream imports
so that box-drawing characters and emoji render correctly regardless of the
active console code page.

Usage:
    python monitor.py [options]
    python monitor.py --help
"""

# Windows stdout/stderr UTF-8 reconfiguration — MUST come before any Rich imports.
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Also enable Virtual Terminal Processing in cmd.exe so ANSI escape codes render.
if sys.platform == "win32":
    import ctypes
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004) on STDOUT (-11)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Not available in some terminal emulators; ignore silently.

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
