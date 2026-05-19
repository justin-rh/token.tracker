---
phase: 05-system-tray
fixed_at: 2026-05-19T00:00:00Z
review_path: .planning/phases/05-system-tray/05-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 5: Code Review Fix Report

**Fixed at:** 2026-05-19
**Source review:** .planning/phases/05-system-tray/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, WR-01, WR-02, WR-03, WR-04)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: `signal.pause()` raises `OSError` on Windows — fallback is unreachable

**Files modified:** `cli/main.py`
**Commit:** 3b671ac
**Applied fix:** Changed `except AttributeError` to `except (AttributeError, OSError)` at both
occurrences — the main wait loop in `_run_monitoring()` (line 282) and the duplicate inside
`_run_table_view()` (line 603). Updated the inline comment to accurately describe the Windows
behaviour.

---

### WR-01: `_quit()` may call `icon.stop()` twice — no double-stop guard in `TrayManager.stop()`

**Files modified:** `ui/tray_manager.py`
**Commit:** 1af4ed0
**Applied fix:** Added `self._stopped = False` to `__init__` and updated `stop()` to guard with
`if self._icon is not None and not self._stopped`, setting `self._stopped = True` before calling
`self._icon.stop()`. The method is now idempotent; a second call from the outer finally block
after `_quit()` has already stopped the icon is a no-op.

---

### WR-02: `update()` docstring claims a `visible` guard that is not implemented

**Files modified:** `ui/tray_manager.py`
**Commit:** 9cae67e
**Applied fix:** Removed the misleading line "Guards on self._icon.visible (Pitfall 4: setter
no-ops if not visible)." from the `update()` docstring. The remaining docstring accurately
describes the only guard that is actually present (`self._icon is None`).

---

### WR-03: `validate_cli_environment()` checks for `watchdog` which is not in `pyproject.toml`

**Files modified:** `cli/main.py`
**Commit:** e0582bc
**Applied fix:** Removed `"watchdog"` from the `required_modules` list. Investigation confirmed
it is not imported or used anywhere in the codebase and is absent from `pyproject.toml`
dependencies — the check was stale from an earlier phase.

---

### WR-04: `KeyboardInterrupt` in `_run_monitoring()` outer except does not stop tray icon

**Files modified:** `cli/main.py`
**Commit:** ee9de0d
**Applied fix:** Added tray cleanup to the outer `except KeyboardInterrupt` handler using the
same `locals()` guard and `contextlib.suppress(Exception)` pattern used by the inner finally
block. This prevents a ghost tray icon when the inner finally block itself raises and is skipped.

---

_Fixed: 2026-05-19_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
