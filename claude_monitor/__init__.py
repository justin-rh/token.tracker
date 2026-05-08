"""claude_monitor namespace shim — meta-path finder (Python 3.12 compatible).

Installs a sys.meta_path finder using the modern find_spec / exec_module API
(find_module was silently dropped in CPython 3.12) that redirects any
``import claude_monitor.X.Y.Z`` to ``import X.Y.Z``.

This lets the upstream source (which uses ``from claude_monitor.data.reader
import ...`` everywhere) work correctly when all modules live flat at the repo
root, without an editable install and without eager circular imports.
"""

import importlib
import importlib.abc
import importlib.machinery
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so flat imports resolve.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from _version import __version__  # noqa: E402

__all__ = ["__version__"]

_PREFIX = "claude_monitor."
_PREFIX_LEN = len(_PREFIX)


class _ClaudeMonitorLoader(importlib.abc.Loader):
    """Load a claude_monitor.X.Y module by importing X.Y instead."""

    def __init__(self, flat_name: str) -> None:
        self._flat_name = flat_name

    def create_module(self, spec):  # noqa: ANN001
        """Return the flat module so both names share one object."""
        flat = importlib.import_module(self._flat_name)
        # Register under the claude_monitor.* name so Python's machinery
        # finds it in sys.modules on the next lookup.
        sys.modules[spec.name] = flat
        return flat

    def exec_module(self, module) -> None:  # noqa: ANN001
        """No-op: create_module already populated the module."""


class _ClaudeMonitorFinder(importlib.abc.MetaPathFinder):
    """Intercept ``claude_monitor.X.Y`` imports and redirect to ``X.Y``."""

    def find_spec(self, fullname: str, path, target=None):  # noqa: ANN001
        if not fullname.startswith(_PREFIX):
            return None
        flat_name = fullname[_PREFIX_LEN:]
        # Return a spec backed by our loader.
        return importlib.machinery.ModuleSpec(
            fullname,
            _ClaudeMonitorLoader(flat_name),
            is_package=self._is_package(flat_name),
        )

    @staticmethod
    def _is_package(name: str) -> bool:
        try:
            spec = importlib.util.find_spec(name)
            return spec is not None and spec.submodule_search_locations is not None
        except (ModuleNotFoundError, ValueError):
            return False


# Install once — guard against double-installation on reload.
if not any(isinstance(f, _ClaudeMonitorFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _ClaudeMonitorFinder())
