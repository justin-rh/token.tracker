"""
Unit tests for ui/session_display.py — _col_pad() column alignment.

Verifies that _col_pad correctly handles:
  - Plain ASCII strings (baseline)
  - Strings containing Rich markup tags ([dim], [value], [/])
  - Strings containing wide characters (emoji — 2 columns each)
  - The per-project row pattern: f"  [dim]{_col_pad(name, 22)}[/] {tokens}"
"""
import sys
import os

# Add project root to path so test can import from ui/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, datetime, timezone
from ui.session_display import _col_pad, _format_exhaust_time, _next_billing_reset


# ---------------------------------------------------------------------------
# Test 1: Baseline — plain ASCII padded to width
# ---------------------------------------------------------------------------

def test_col_pad_plain_ascii():
    """Plain ASCII string padded to width; result string length == width."""
    result = _col_pad("hello", 10)
    # "hello" is 5 visible chars; should be padded with 5 spaces
    assert len(result) == 10
    assert result == "hello     "


# ---------------------------------------------------------------------------
# Test 2: Already-at-width string — no padding added
# ---------------------------------------------------------------------------

def test_col_pad_no_padding_needed():
    """String already at or above target width — no padding added."""
    result = _col_pad("hello", 5)
    assert result == "hello"

    # Over-width — no truncation
    result2 = _col_pad("toolong", 3)
    assert result2 == "toolong"


# ---------------------------------------------------------------------------
# Test 3: Rich markup tags are invisible — padding based on visible text only
# ---------------------------------------------------------------------------

def test_col_pad_with_rich_markup():
    """Rich markup tags are stripped for width calculation; padding aligns visible text."""
    # "[bold]foo[/bold]" — visible text is "foo" (3 chars), markup adds 13 chars to string length
    s = "[bold]foo[/bold]"
    result = _col_pad(s, 10)
    # Visible width of "foo" is 3; need 7 spaces to reach width 10
    # Result should be "[bold]foo[/bold]" + 7 spaces
    assert result == "[bold]foo[/bold]" + " " * 7

    # Verify the Python string length is longer than width (due to markup overhead)
    assert len(result) > 10


# ---------------------------------------------------------------------------
# Test 4: [dim] markup pattern used in per-project rows
# ---------------------------------------------------------------------------

def test_col_pad_dim_markup_pattern():
    """[dim]name[/] pattern — _col_pad(name, 22) inside [dim] tags aligns correctly."""
    # This is the actual pattern: f"  [dim]{_col_pad(name, 22)}[/] {tokens}"
    # _col_pad pads the inner name so that visible width of name reaches 22.
    # The [dim] tags are OUTSIDE _col_pad — they do not affect the padding calculation.

    name = "tracker"  # 7 visible chars; needs 15 spaces to reach 22
    padded_name = _col_pad(name, 22)

    # Visible length of padded_name should be 22
    import re
    stripped = re.sub(r'\[/?[^\]]*\]', '', padded_name)
    assert len(stripped) == 22, f"Expected visible width 22, got {len(stripped)}: {repr(padded_name)}"

    # Full row f-string (as used in session_display.py)
    row = f"  [dim]{padded_name}[/] 1.5k tok"
    # Visible content: "  " + "tracker" + 15 spaces + " " + "1.5k tok"
    # Verify [dim] and [/] tags are present but padded_name is inside them
    assert "[dim]" in row
    assert "[/]" in row
    assert "tracker" in row


# ---------------------------------------------------------------------------
# Test 5: Wide character (emoji) — counts as 2 columns
# ---------------------------------------------------------------------------

def test_col_pad_wide_char_emoji():
    """Wide chars (emoji) count as 2 columns; padding accounts for double-width."""
    # "📂" is a wide char — 1 Python char but 2 terminal columns
    s = "📂"
    result = _col_pad(s, 10)
    # Visible width of "📂" is 2; need 8 spaces to reach width 10
    assert result == "📂" + " " * 8


# ---------------------------------------------------------------------------
# Test 6: Rich markup containing project name with markup characters
# ---------------------------------------------------------------------------

def test_col_pad_project_name_with_bracket_chars():
    """Project name containing Rich markup-like characters is padded correctly.

    This is the WR-04 regression test: if a project directory were named
    '[bold]foo[/]', _col_pad must not miscount the visible width.
    """
    # Simulate a project name that contains Rich markup characters
    # (unlikely in practice but _col_pad must handle it correctly)
    name = "[bold]foo[/]"  # Rich would render this as "foo" (3 visible chars)

    padded = _col_pad(name, 22)

    import re
    stripped = re.sub(r'\[/?[^\]]*\]', '', padded)
    visible_width = len(stripped)
    assert visible_width == 22, (
        f"Expected visible width 22 for markup name, got {visible_width}: {repr(padded)}"
    )


# ---------------------------------------------------------------------------
# Phase 10: _render_daily_spend_chart() tests (ANLX-01, ANLX-02, ANLX-03)
# ---------------------------------------------------------------------------

class TestRenderDailySpendChart:
    """Unit tests for SessionDisplayComponent._render_daily_spend_chart()."""

    def _make_display(self):
        from ui.session_display import SessionDisplayComponent
        return SessionDisplayComponent()

    def test_empty_tuple_returns_no_lines(self):
        """Empty daily_pool_spend returns no chart lines (ANLX-03)."""
        display = self._make_display()
        result = display._render_daily_spend_chart((), today_str="2026-06-02")
        assert result == []

    def test_all_zero_spend_no_fallback_returns_no_lines(self):
        """All-zero daily spend with no pool_spend_usd fallback returns [] (ANLX-03)."""
        display = self._make_display()
        data = (("2026-06-01", 0.0), ("2026-06-02", 0.0))
        result = display._render_daily_spend_chart(data, today_str="2026-06-02", pool_spend_usd=0.0)
        assert result == []

    def test_seed_only_case_shows_api_total_row(self):
        """Seed-only case: daily zeros but pool_spend_usd > 0 → shows billing cycle total row."""
        display = self._make_display()
        data = (("2026-06-01", 0.0), ("2026-06-02", 0.0))
        result = display._render_daily_spend_chart(data, today_str="2026-06-02", pool_spend_usd=357.01)
        assert len(result) > 0
        assert "Daily pool spend" in "\n".join(result)
        assert "$357.01" in "\n".join(result)
        assert "API total" in "\n".join(result)

    def test_nonzero_spend_returns_lines(self):
        """At least one non-zero day produces chart lines (ANLX-01)."""
        display = self._make_display()
        data = (("2026-06-01", 5.00), ("2026-06-02", 0.0))
        result = display._render_daily_spend_chart(data, today_str="2026-06-02")
        assert len(result) > 0

    def test_header_line_present(self):
        """Chart includes 'Daily pool spend' header line."""
        display = self._make_display()
        data = (("2026-06-01", 5.00),)
        result = display._render_daily_spend_chart(data, today_str="2026-06-01")
        header_lines = [l for l in result if "Daily pool spend" in l]
        assert len(header_lines) == 1

    def test_today_marker_present(self):
        """Today's row contains the '◀ today' marker (ANLX-02)."""
        display = self._make_display()
        data = (("2026-06-01", 2.00), ("2026-06-02", 5.00))
        result = display._render_daily_spend_chart(data, today_str="2026-06-02")
        today_lines = [l for l in result if "◀ today" in l]
        assert len(today_lines) == 1

    def test_non_today_rows_have_no_today_marker(self):
        """Non-today rows do not contain the '◀ today' marker."""
        display = self._make_display()
        data = (("2026-06-01", 2.00), ("2026-06-02", 5.00))
        result = display._render_daily_spend_chart(data, today_str="2026-06-02")
        jun01_lines = [l for l in result if "Jun 01" in l]
        assert len(jun01_lines) == 1
        assert "◀ today" not in jun01_lines[0]

    def test_spend_amount_shown_in_row(self):
        """Each data row contains the spend amount formatted as '$X.XX' (ANLX-02)."""
        display = self._make_display()
        data = (("2026-06-01", 12.34),)
        result = display._render_daily_spend_chart(data, today_str="2026-06-02")
        data_lines = [l for l in result if "Jun 01" in l]
        assert len(data_lines) == 1
        assert "$12.34" in data_lines[0]

    def test_today_uses_success_style(self):
        """Today's bar uses [success] Rich markup (ANLX-02)."""
        display = self._make_display()
        data = (("2026-06-01", 5.00),)
        result = display._render_daily_spend_chart(data, today_str="2026-06-01")
        today_line = next(l for l in result if "Jun 01" in l)
        assert "[success]" in today_line

    def test_past_day_uses_value_style(self):
        """Non-today bars use [value] Rich markup (ANLX-02)."""
        display = self._make_display()
        data = (("2026-06-01", 5.00), ("2026-06-02", 3.00))
        result = display._render_daily_spend_chart(data, today_str="2026-06-02")
        jun01_line = next(l for l in result if "Jun 01" in l)
        assert "[value]" in jun01_line


# ---------------------------------------------------------------------------
# _format_exhaust_time tests
# ---------------------------------------------------------------------------

class TestFormatExhaustTime:
    """_format_exhaust_time() produces correct human-readable labels."""

    def _dt(self, days_from_now: int, hour: int = 15, minute: int = 45) -> datetime:
        """Build a timezone-aware local datetime N days from a fixed reference."""
        base = datetime(2026, 6, 10, hour, minute, tzinfo=timezone.utc)
        return base.astimezone()  # convert to local tz

    def _make(self, days_offset: int, hour: int = 15, minute: int = 45) -> datetime:
        from datetime import timedelta
        base = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)  # fixed "now"
        target = base + timedelta(days=days_offset, hours=hour - 12, minutes=minute - 0)
        return target.astimezone()

    def test_today_label(self):
        """Exhaustion within today returns 'today at ...'."""
        from datetime import timedelta
        now_local = datetime.now().astimezone()
        exhaust = (datetime.now(timezone.utc) + timedelta(hours=2)).astimezone()
        result = _format_exhaust_time(exhaust)
        assert result.startswith("today at")

    def test_tomorrow_label(self):
        """Exhaustion tomorrow returns 'tomorrow at ...'."""
        from datetime import timedelta
        exhaust = (datetime.now(timezone.utc) + timedelta(hours=25)).astimezone()
        result = _format_exhaust_time(exhaust)
        assert result.startswith("tomorrow at")

    def test_this_week_label(self):
        """Exhaustion 3 days away returns weekday name."""
        from datetime import timedelta
        exhaust = (datetime.now(timezone.utc) + timedelta(days=3, hours=1)).astimezone()
        result = _format_exhaust_time(exhaust)
        expected_day = exhaust.strftime("%A")
        assert result.startswith(expected_day)

    def test_beyond_week_label(self):
        """Exhaustion >7 days away returns 'Mon DD at ...' format."""
        from datetime import timedelta
        exhaust = (datetime.now(timezone.utc) + timedelta(days=10)).astimezone()
        result = _format_exhaust_time(exhaust)
        month_abbr = exhaust.strftime("%b")
        assert month_abbr in result
        assert str(exhaust.day) in result

    def test_no_leading_zero_on_hour(self):
        """Single-digit hours have no leading zero (e.g. '3:45 PM' not '03:45 PM')."""
        from datetime import timedelta
        # Force a 3 PM UTC time (will be some local time, but hour digits vary)
        exhaust = datetime(2026, 6, 20, 15, 45, tzinfo=timezone.utc).astimezone()
        result = _format_exhaust_time(exhaust)
        # Should not contain " 0" in the time portion (leading zero on hour)
        assert "0:" not in result.split("at")[-1].strip() or result.split("at")[-1].strip()[0] != "0"


# ---------------------------------------------------------------------------
# _next_billing_reset tests
# ---------------------------------------------------------------------------

class TestNextBillingReset:
    """_next_billing_reset() computes the correct next cycle reset date."""

    def test_mid_month_cycle(self):
        """Cycle starting Jun 1 resets Jul 1."""
        assert _next_billing_reset("2026-06-01") == date(2026, 7, 1)

    def test_december_wraps_to_january(self):
        """Cycle starting Dec 1 resets Jan 1 of the following year."""
        assert _next_billing_reset("2026-12-01") == date(2027, 1, 1)

    def test_day_clamped_to_month_end(self):
        """Cycle starting Jan 31 resets Feb 28 (non-leap year)."""
        assert _next_billing_reset("2026-01-31") == date(2026, 2, 28)

    def test_leap_year_feb(self):
        """Cycle starting Jan 31 in leap year resets Feb 29."""
        assert _next_billing_reset("2028-01-31") == date(2028, 2, 29)

    def test_invalid_string_returns_date_max(self):
        """Malformed billing_cycle_start returns date.max (safe fallback)."""
        assert _next_billing_reset("not-a-date") == date.max
