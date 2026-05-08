"""claude_monitor namespace shim.

This package provides the `claude_monitor` namespace so that upstream import
statements (e.g. `from claude_monitor.data.reader import ...`) resolve correctly
when running from the repo root without an editable install.

All real source modules live at the repo root level (data/, core/, monitoring/,
ui/, cli/, terminal/, utils/).  This __init__.py registers them under the
claude_monitor.* namespace by aliasing sys.modules entries.
"""

import importlib
import sys
import types
from pathlib import Path

# Ensure the repo root is on sys.path so flat imports resolve.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from _version import __version__  # noqa: E402

__all__ = ["__version__"]

# Sub-packages to alias under the claude_monitor namespace.
_SUBPACKAGES = [
    "data",
    "core",
    "monitoring",
    "ui",
    "cli",
    "terminal",
    "utils",
]

# Modules that live at the repo root (not in a sub-package).
_ROOT_MODULES = [
    "error_handling",
    "_version",
]


def _register_aliases() -> None:
    """Register flat modules under the claude_monitor.* namespace."""
    pkg = sys.modules[__name__]

    # Register root-level modules as claude_monitor.<name>
    for mod_name in _ROOT_MODULES:
        fq_name = f"claude_monitor.{mod_name}"
        if fq_name not in sys.modules:
            try:
                mod = importlib.import_module(mod_name)
                sys.modules[fq_name] = mod
            except ImportError:
                pass

    # Register sub-packages and their children as claude_monitor.<pkg>.*
    for sub in _SUBPACKAGES:
        fq_sub = f"claude_monitor.{sub}"
        if fq_sub not in sys.modules:
            try:
                mod = importlib.import_module(sub)
                sys.modules[fq_sub] = mod
                setattr(pkg, sub, mod)
            except ImportError:
                pass

        # Walk already-imported sub-modules and alias them.
        prefix = f"{sub}."
        for key, value in list(sys.modules.items()):
            if key.startswith(prefix) and not key.startswith("claude_monitor."):
                alias = f"claude_monitor.{key}"
                if alias not in sys.modules:
                    sys.modules[alias] = value


_register_aliases()
