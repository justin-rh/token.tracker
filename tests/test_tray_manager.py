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

    def test_no_hwnd_returns_without_installing_handler(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = 0
            tray._install_close_guard()
        assert tray._ctrl_handler_cb is None

    def test_no_hwnd_does_not_call_set_console_ctrl_handler(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = 0
            tray._install_close_guard()
        mock_windll.kernel32.SetConsoleCtrlHandler.assert_not_called()


class TestInstallCloseGuardShellContext:
    """_install_close_guard() when the console is shared with a parent shell (count > 1)."""

    def test_shared_console_returns_without_installing_handler(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        fake_hwnd = 0xABCD

        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = fake_hwnd
            mock_windll.kernel32.GetConsoleProcessList.return_value = 2
            tray._install_close_guard()

        assert tray._ctrl_handler_cb is None

    def test_shared_console_does_not_call_set_console_ctrl_handler(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        fake_hwnd = 0xABCD

        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = fake_hwnd
            mock_windll.kernel32.GetConsoleProcessList.return_value = 2
            tray._install_close_guard()

        mock_windll.kernel32.SetConsoleCtrlHandler.assert_not_called()


class TestInstallCloseGuardOwnsConsole:
    """_install_close_guard() when this process is the sole owner of the console (count=1)."""

    def _make_tray_with_own_console(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        fake_hwnd = 0xABCD

        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GetConsoleWindow.return_value = fake_hwnd
            mock_windll.kernel32.GetConsoleProcessList.return_value = 1
            mock_windll.kernel32.SetConsoleCtrlHandler.return_value = True
            tray._install_close_guard()

        return tray, fake_hwnd, mock_windll

    def test_ctrl_handler_cb_stored_as_instance_attr(self):
        tray, _, _ = self._make_tray_with_own_console()
        assert tray._ctrl_handler_cb is not None

    def test_set_console_ctrl_handler_called_with_add_true(self):
        tray, fake_hwnd, mock_windll = self._make_tray_with_own_console()
        call_args = mock_windll.kernel32.SetConsoleCtrlHandler.call_args
        assert call_args is not None
        _, add_arg = call_args[0]
        assert add_arg is True


class TestInstallCloseGuardConstants:
    """Module-level constants for the close guard must exist with correct values."""

    def test_ctrl_close_event_value(self):
        from claude_monitor.ui.tray_manager import CTRL_CLOSE_EVENT
        assert CTRL_CLOSE_EVENT == 2

    def test_handler_routine_is_callable(self):
        from claude_monitor.ui.tray_manager import _HandlerRoutine
        assert callable(_HandlerRoutine)

    def test_init_sets_ctrl_handler_cb_to_none(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        assert tray._ctrl_handler_cb is None


class TestCloseGuard:
    """Tests for TrayManager._install_close_guard() guard logic and callback behavior."""

    def _make_tray(self):
        from claude_monitor.ui.tray_manager import TrayManager
        return TrayManager(shutdown_callback=lambda: None)

    def test_no_hwnd_skips_handler(self):
        tray = self._make_tray()
        with patch("claude_monitor.ui.tray_manager.ctypes") as mock_ctypes:
            mock_ctypes.windll.kernel32.GetConsoleWindow.return_value = 0
            tray._install_close_guard()
        assert tray._ctrl_handler_cb is None

    def test_shared_console_skips_handler(self):
        tray = self._make_tray()
        with patch("claude_monitor.ui.tray_manager.ctypes") as mock_ctypes:
            mock_ctypes.windll.kernel32.GetConsoleWindow.return_value = 0x1234
            mock_ctypes.windll.kernel32.GetConsoleProcessList.return_value = 2
            tray._install_close_guard()
        assert tray._ctrl_handler_cb is None

    def test_sole_owner_installs_handler(self):
        from claude_monitor.ui.tray_manager import TrayManager
        tray = TrayManager(shutdown_callback=lambda: None)
        fake_hwnd = 0xABCD

        with (
            patch("claude_monitor.ui.tray_manager.ctypes.windll.kernel32") as kern32,
            patch("claude_monitor.ui.tray_manager.ctypes.windll.user32"),
            patch("claude_monitor.ui.tray_manager._HandlerRoutine") as mock_hr,
        ):
            kern32.GetConsoleWindow.return_value = fake_hwnd
            kern32.GetConsoleProcessList.return_value = 1
            kern32.SetConsoleCtrlHandler.return_value = True
            mock_hr.return_value = MagicMock()

            tray._install_close_guard()

            kern32.SetConsoleCtrlHandler.assert_called_once_with(
                mock_hr.return_value, True
            )
            assert tray._ctrl_handler_cb is not None

    def test_ctrl_close_event_hides_window_and_returns_true(self):
        from claude_monitor.ui.tray_manager import CTRL_CLOSE_EVENT, SW_HIDE
        fake_hwnd = 0xABCD

        with (
            patch("claude_monitor.ui.tray_manager.ctypes.windll.kernel32") as kern32,
            patch("claude_monitor.ui.tray_manager.ctypes.windll.user32") as user32,
        ):
            kern32.GetConsoleWindow.return_value = fake_hwnd
            kern32.GetConsoleProcessList.return_value = 1
            kern32.SetConsoleCtrlHandler.return_value = True

            tray = self._make_tray()
            tray._install_close_guard()

            captured_cb = kern32.SetConsoleCtrlHandler.call_args[0][0]
            user32.ShowWindow.reset_mock()

            result = captured_cb(CTRL_CLOSE_EVENT)

            user32.ShowWindow.assert_called_once_with(fake_hwnd, SW_HIDE)
            assert result is True

    def test_other_ctrl_event_returns_false(self):
        from claude_monitor.ui.tray_manager import CTRL_CLOSE_EVENT
        CTRL_C_EVENT = 0
        fake_hwnd = 0xABCD

        with (
            patch("claude_monitor.ui.tray_manager.ctypes.windll.kernel32") as kern32,
            patch("claude_monitor.ui.tray_manager.ctypes.windll.user32") as user32,
        ):
            kern32.GetConsoleWindow.return_value = fake_hwnd
            kern32.GetConsoleProcessList.return_value = 1
            kern32.SetConsoleCtrlHandler.return_value = True

            tray = self._make_tray()
            tray._install_close_guard()

            captured_cb = kern32.SetConsoleCtrlHandler.call_args[0][0]
            user32.ShowWindow.reset_mock()

            result = captured_cb(CTRL_C_EVENT)

            user32.ShowWindow.assert_not_called()
            assert result is False
