"""Tests for ui/tray_manager.py — TDD RED phase.

Tests cover pure-logic functions only (no pystray Icon instantiation):
  - _utilization_to_color() thresholds
  - TrayManager._make_icon_image() returns correct RGBA Image with correct color
  - TrayManager._build_tooltip() format + length guard
  - TrayManager.update() with _icon = None must not raise
  - TrayManager._install_close_guard() PID guard and WNDPROC subclassing
"""
import ctypes
import os
from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest


class TestUtilizationToColor:
    """_utilization_to_color() maps pct to green/yellow/red thresholds."""

    def test_zero_returns_green(self):
        from claude_monitor.ui.tray_manager import _utilization_to_color
        assert _utilization_to_color(0.0) == (34, 197, 94)

    def test_below_50_returns_green(self):
        from claude_monitor.ui.tray_manager import _utilization_to_color
        assert _utilization_to_color(49.9) == (34, 197, 94)

    def test_exactly_50_returns_yellow(self):
        from claude_monitor.ui.tray_manager import _utilization_to_color
        assert _utilization_to_color(50.0) == (234, 179, 8)

    def test_below_75_returns_yellow(self):
        from claude_monitor.ui.tray_manager import _utilization_to_color
        assert _utilization_to_color(74.9) == (234, 179, 8)

    def test_exactly_75_returns_red(self):
        from claude_monitor.ui.tray_manager import _utilization_to_color
        assert _utilization_to_color(75.0) == (239, 68, 68)

    def test_100_returns_red(self):
        from claude_monitor.ui.tray_manager import _utilization_to_color
        assert _utilization_to_color(100.0) == (239, 68, 68)


class TestMakeIconImage:
    """TrayManager._make_icon_image() returns correct RGBA PIL Image."""

    def _get_center_pixel(self, img):
        """Return the RGBA pixel at the center of the image."""
        return img.getpixel((32, 32))

    def test_green_image_size_and_mode(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        img = tray._make_icon_image(0.0)
        assert img.size == (64, 64)
        assert img.mode == "RGBA"

    def test_green_center_pixel(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        img = tray._make_icon_image(0.0)
        r, g, b, a = self._get_center_pixel(img)
        assert (r, g, b) == (34, 197, 94)
        assert a == 255

    def test_yellow_center_pixel(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        img = tray._make_icon_image(60.0)
        r, g, b, a = self._get_center_pixel(img)
        assert (r, g, b) == (234, 179, 8)

    def test_red_center_pixel(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        img = tray._make_icon_image(80.0)
        r, g, b, a = self._get_center_pixel(img)
        assert (r, g, b) == (239, 68, 68)


class TestBuildTooltip:
    """TrayManager._build_tooltip() format and length constraints."""

    def test_with_values_contains_pct_and_time(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        tip = tray._build_tooltip(67.3, datetime(2026, 5, 19, 14, 32, 7))
        assert "67.3%" in tip
        assert "14:32:07" in tip

    def test_with_values_length_under_128(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        tip = tray._build_tooltip(67.3, datetime(2026, 5, 19, 14, 32, 7))
        assert len(tip) < 128

    def test_none_values_contains_dashes_and_never(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        tip = tray._build_tooltip(None, None)
        assert "--" in tip
        assert "never" in tip

    def test_none_values_length_under_128(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        tip = tray._build_tooltip(None, None)
        assert len(tip) < 128


class TestUpdateWithNoIcon:
    """TrayManager.update() with _icon = None must not raise."""

    def test_update_with_none_icon_does_not_raise(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        # _icon is None by default (before start() is called)
        assert tray._icon is None
        # Must return without raising
        tray.update(50.0, None)


class TestInstallCloseGuardNoConsole:
    """_install_close_guard() when GetConsoleWindow() returns 0 (no console)."""

    def test_no_hwnd_returns_without_subclassing(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = 0
            tray._install_close_guard()
        # No subclassing occurred — callback and original proc remain defaults
        assert tray._wndproc_cb is None
        assert tray._original_wndproc == 0

    def test_no_hwnd_does_not_call_set_window_long_ptr(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = 0
            tray._install_close_guard()
        mock_windll.user32.SetWindowLongPtrW.assert_not_called()


class TestInstallCloseGuardShellContext:
    """_install_close_guard() when the console window is owned by the shell (PID mismatch)."""

    def test_foreign_pid_returns_without_subclassing(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        fake_hwnd = 0xABCD
        foreign_pid = os.getpid() + 9999  # guaranteed different from ours

        def fake_get_window_thread_process_id(hwnd, pid_ptr):
            # Write the foreign PID into the byref pointer
            pid_ptr._obj.value = foreign_pid
            return 1

        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = fake_hwnd
            mock_windll.user32.GetWindowThreadProcessId.side_effect = (
                fake_get_window_thread_process_id
            )
            tray._install_close_guard()

        assert tray._wndproc_cb is None
        assert tray._original_wndproc == 0

    def test_foreign_pid_does_not_call_set_window_long_ptr(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        fake_hwnd = 0xABCD
        foreign_pid = os.getpid() + 9999

        def fake_get_window_thread_process_id(hwnd, pid_ptr):
            pid_ptr._obj.value = foreign_pid
            return 1

        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = fake_hwnd
            mock_windll.user32.GetWindowThreadProcessId.side_effect = (
                fake_get_window_thread_process_id
            )
            tray._install_close_guard()

        mock_windll.user32.SetWindowLongPtrW.assert_not_called()


class TestInstallCloseGuardOwnsConsole:
    """_install_close_guard() when this process owns the console window."""

    def _make_tray_with_own_console(self):
        """Return a TrayManager and the mock_windll after _install_close_guard() runs."""
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        fake_hwnd = 0xABCD
        our_pid = os.getpid()
        fake_original_proc = 0x1234

        def fake_get_window_thread_process_id(hwnd, pid_ptr):
            pid_ptr._obj.value = our_pid
            return 1

        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = fake_hwnd
            mock_windll.user32.GetWindowThreadProcessId.side_effect = (
                fake_get_window_thread_process_id
            )
            mock_windll.user32.SetWindowLongPtrW.return_value = fake_original_proc
            tray._install_close_guard()

        return tray, fake_hwnd, fake_original_proc

    def test_wndproc_cb_stored_as_instance_attr(self):
        tray, _, _ = self._make_tray_with_own_console()
        assert tray._wndproc_cb is not None

    def test_original_wndproc_stored_from_set_window_long_ptr_return(self):
        tray, _, fake_original_proc = self._make_tray_with_own_console()
        assert tray._original_wndproc == fake_original_proc

    def test_set_window_long_ptr_called_with_gwlp_wndproc(self):
        from claude_monitor.ui.tray_manager import TrayManager, GWLP_WNDPROC
        tray = TrayManager(shutdown_callback=lambda: None)
        fake_hwnd = 0xABCD
        our_pid = os.getpid()

        def fake_get_window_thread_process_id(hwnd, pid_ptr):
            pid_ptr._obj.value = our_pid
            return 1

        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = fake_hwnd
            mock_windll.user32.GetWindowThreadProcessId.side_effect = (
                fake_get_window_thread_process_id
            )
            mock_windll.user32.SetWindowLongPtrW.return_value = 0x1234
            tray._install_close_guard()

        call_args = mock_windll.user32.SetWindowLongPtrW.call_args
        assert call_args is not None
        hwnd_arg, index_arg, _ = call_args[0]
        assert hwnd_arg == fake_hwnd
        assert index_arg == GWLP_WNDPROC


class TestInstallCloseGuardConstants:
    """Module-level constants WM_CLOSE, GWLP_WNDPROC, SW_SHOW must exist with correct values."""

    def test_wm_close_value(self):
        from claude_monitor.ui.tray_manager import WM_CLOSE
        assert WM_CLOSE == 0x0010

    def test_gwlp_wndproc_value(self):
        from claude_monitor.ui.tray_manager import GWLP_WNDPROC
        assert GWLP_WNDPROC == -4

    def test_sw_show_value(self):
        from claude_monitor.ui.tray_manager import SW_SHOW
        assert SW_SHOW == 5

    def test_wndproc_type_is_winfunctype(self):
        from claude_monitor.ui.tray_manager import WNDPROC
        # WINFUNCTYPE creates a callable type; verify it is callable (i.e. a type)
        assert callable(WNDPROC)

    def test_init_sets_wndproc_cb_to_none(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        assert tray._wndproc_cb is None

    def test_init_sets_original_wndproc_to_zero(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        assert tray._original_wndproc == 0
