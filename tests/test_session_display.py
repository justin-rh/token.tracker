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

from ui.session_display import _col_pad


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
