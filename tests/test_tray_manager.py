"""Tests for ui/tray_manager.py — TDD RED phase.

Tests cover pure-logic functions only (no pystray Icon instantiation):
  - _utilization_to_color() thresholds
  - TrayManager._make_icon_image() returns correct RGBA Image with correct color
  - TrayManager._build_tooltip() format + length guard
  - TrayManager.update() with _icon = None must not raise
"""
from datetime import datetime

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
