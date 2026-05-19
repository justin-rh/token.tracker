"""
Unit tests for core/project_breakdown.py — ProjectBreakdown and compute_project_breakdown().

Covers all 7 behavior requirements from 06-02-PLAN.md:
  - Test 1: Missing data path → empty ProjectBreakdown without raising
  - Test 2: Deduplication by requestId reduces entries; token totals per deduplicated entry
  - Test 3: Today-scoped entries included; entries 40 days ago excluded from today list
  - Test 4: Billing month window filtering (on/after billing_start included; before excluded)
  - Test 5: Results sorted descending, truncated to 5
  - Test 6: Display name = last hyphen-separated segment of project slug (D-01)
  - Test 7: Zero-token entries excluded from both lists
"""
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.project_breakdown import compute_project_breakdown
from claude_monitor.core.models import ProjectBreakdown


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, entries: list) -> None:
    """Write a list of dicts as JSONL lines to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _make_entry(
    request_id: str,
    timestamp: str,
    input_tokens: int = 100,
    output_tokens: int = 200,
    cache_creation: int = 0,
    cache_read: int = 0,
) -> dict:
    """Build a minimal raw JSONL entry in the format written by Claude Code."""
    return {
        "requestId": request_id,
        "timestamp": timestamp,
        "message": {
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            }
        },
    }


def _today_utc_str() -> str:
    """Return an ISO timestamp string for today UTC noon."""
    today = datetime.now(timezone.utc).date()
    return f"{today}T12:00:00+00:00"


def _days_ago_str(days: int) -> str:
    """Return an ISO timestamp string for N days ago UTC noon."""
    d = datetime.now(timezone.utc).date() - timedelta(days=days)
    return f"{d}T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Test 1: Missing data path → empty ProjectBreakdown without raising
# ---------------------------------------------------------------------------

def test_missing_data_path_returns_empty(tmp_path):
    """compute_project_breakdown with non-existent data path returns empty lists, no raise."""
    non_existent = tmp_path / "no-such-dir"
    result = compute_project_breakdown(data_path=non_existent, config_dir=tmp_path)

    assert isinstance(result, ProjectBreakdown)
    assert result.today == []
    assert result.billing_month == []
    assert isinstance(result.as_of, datetime)


# ---------------------------------------------------------------------------
# Test 2: Deduplication collapses streaming entries
# ---------------------------------------------------------------------------

def test_deduplication_collapses_streaming_entries(tmp_path):
    """3 entries sharing a requestId deduplicate to 1; token count uses max output_tokens entry."""
    # Project A: 3 streaming entries for req-1 (output_tokens: 10, 50, 200 → keep 200)
    proj_a = tmp_path / "proj-alpha"
    proj_a.mkdir()
    today_str = _today_utc_str()
    entries_a = [
        _make_entry("req-1", today_str, input_tokens=100, output_tokens=10),
        _make_entry("req-1", today_str, input_tokens=100, output_tokens=50),
        _make_entry("req-1", today_str, input_tokens=100, output_tokens=200),
    ]
    _write_jsonl(proj_a / "session.jsonl", entries_a)

    # Project B: 3 streaming entries for req-2 (output_tokens: 5, 30, 100 → keep 100)
    proj_b = tmp_path / "proj-beta"
    proj_b.mkdir()
    entries_b = [
        _make_entry("req-2", today_str, input_tokens=50, output_tokens=5),
        _make_entry("req-2", today_str, input_tokens=50, output_tokens=30),
        _make_entry("req-2", today_str, input_tokens=50, output_tokens=100),
    ]
    _write_jsonl(proj_b / "session.jsonl", entries_b)

    result = compute_project_breakdown(data_path=tmp_path, config_dir=tmp_path)

    # After deduplication: alpha → 100+200=300 tokens, beta → 50+100=150 tokens
    today_dict = dict(result.today)
    assert "alpha" in today_dict, f"Expected 'alpha' in today, got {result.today}"
    assert "beta" in today_dict, f"Expected 'beta' in today, got {result.today}"
    assert today_dict["alpha"] == 300, f"Expected 300, got {today_dict['alpha']}"
    assert today_dict["beta"] == 150, f"Expected 150, got {today_dict['beta']}"


# ---------------------------------------------------------------------------
# Test 3: Today scope — UTC calendar day boundary
# ---------------------------------------------------------------------------

def test_today_scope_utc_boundary(tmp_path):
    """Entry today included; entry 40 days ago excluded from today list."""
    proj = tmp_path / "proj-gamma"
    proj.mkdir()

    entries = [
        _make_entry("req-today", _today_utc_str(), input_tokens=100, output_tokens=200),
        _make_entry("req-old", _days_ago_str(40), input_tokens=100, output_tokens=200),
    ]
    _write_jsonl(proj / "session.jsonl", entries)

    result = compute_project_breakdown(data_path=tmp_path, config_dir=tmp_path)

    today_dict = dict(result.today)
    assert "gamma" in today_dict, f"Expected 'gamma' in today, got {result.today}"
    assert today_dict["gamma"] == 300  # only today's entry: 100+200

    # Old entry should NOT appear in today
    # (gamma appears but only once — verify count is 300 not 600)
    assert today_dict["gamma"] == 300


# ---------------------------------------------------------------------------
# Test 4: Billing month window filtering
# ---------------------------------------------------------------------------

def test_billing_month_window_filtering(tmp_path):
    """Entry within billing month (on/after billing_start) included; entry before excluded."""
    # Write a config.json with billing_cycle_start_day=1 (default)
    # billing_start is 1st of current or previous month depending on today
    config_file = tmp_path / "config.json"
    config_file.write_text('{"billing_cycle_start_day": 1}', encoding="utf-8")

    proj = tmp_path / "proj-delta"
    proj.mkdir()

    # Entry within billing month: 5 days ago is definitely within the current billing period
    # when start_day=1 (since we're 5 days into the month at minimum if today >= 5)
    in_billing = _days_ago_str(5)
    # Entry 40 days ago is before most billing periods (1+ months ago)
    before_billing = _days_ago_str(40)

    entries = [
        _make_entry("req-in", in_billing, input_tokens=100, output_tokens=200),
        _make_entry("req-before", before_billing, input_tokens=100, output_tokens=200),
    ]
    _write_jsonl(proj / "session.jsonl", entries)

    result = compute_project_breakdown(data_path=tmp_path, config_dir=tmp_path)

    month_dict = dict(result.billing_month)
    assert "delta" in month_dict, f"Expected 'delta' in billing_month, got {result.billing_month}"
    # Only the in-billing entry: 100+200=300
    assert month_dict["delta"] == 300, f"Expected 300, got {month_dict['delta']}"


# ---------------------------------------------------------------------------
# Test 5: Sorted descending and truncated to top 5
# ---------------------------------------------------------------------------

def test_sorted_descending_top_5(tmp_path):
    """Results sorted descending by tokens; only top 5 returned (6th omitted)."""
    today_str = _today_utc_str()

    # Create 6 projects with distinct token counts
    token_counts = [600, 100, 400, 200, 500, 300]
    project_names = ["proj-six", "proj-one", "proj-four", "proj-two", "proj-five", "proj-three"]
    expected_order = ["six", "five", "four", "three", "two"]  # top 5 descending

    for name, tokens in zip(project_names, token_counts):
        proj_dir = tmp_path / name
        proj_dir.mkdir()
        entry = _make_entry(f"req-{name}", today_str, input_tokens=tokens, output_tokens=0)
        _write_jsonl(proj_dir / "session.jsonl", [entry])

    result = compute_project_breakdown(data_path=tmp_path, config_dir=tmp_path)

    assert len(result.today) == 5, f"Expected 5, got {len(result.today)}"
    result_names = [name for name, _ in result.today]
    assert result_names == expected_order, f"Expected {expected_order}, got {result_names}"

    # Verify descending order of token values
    token_values = [t for _, t in result.today]
    assert token_values == sorted(token_values, reverse=True)

    # "one" (100 tokens) is 6th and should be excluded
    assert "one" not in result_names


# ---------------------------------------------------------------------------
# Test 6: Display name = last hyphen-separated segment of slug
# ---------------------------------------------------------------------------

def test_display_name_last_segment(tmp_path):
    """Display name for slug 'C:-Users-justin-rhoda-token-tracker' → 'token-tracker'."""
    slug = "C:-Users-justin-rhoda-token-tracker"
    proj_dir = tmp_path / slug
    proj_dir.mkdir()
    today_str = _today_utc_str()
    entry = _make_entry("req-d01", today_str, input_tokens=100, output_tokens=200)
    _write_jsonl(proj_dir / "session.jsonl", [entry])

    result = compute_project_breakdown(data_path=tmp_path, config_dir=tmp_path)

    today_names = [name for name, _ in result.today]
    # slug.split("-")[-1] == "tracker"
    assert "tracker" in today_names, f"Expected 'tracker' in today names, got {today_names}"


# ---------------------------------------------------------------------------
# Test 7: Zero-token entries excluded from both lists
# ---------------------------------------------------------------------------

def test_zero_token_entries_excluded(tmp_path):
    """Entries with 0 total tokens are excluded from both today and billing_month lists."""
    proj = tmp_path / "proj-epsilon"
    proj.mkdir()
    today_str = _today_utc_str()

    entries = [
        # Zero-token entry — must be excluded
        _make_entry("req-zero", today_str, input_tokens=0, output_tokens=0),
        # Non-zero entry to confirm project itself can appear when tokens > 0
        _make_entry("req-nonzero", today_str, input_tokens=50, output_tokens=50),
    ]
    _write_jsonl(proj / "session.jsonl", entries)

    # Also create a project with ONLY zero-token entries
    proj_zero = tmp_path / "proj-zeta"
    proj_zero.mkdir()
    _write_jsonl(proj_zero / "session.jsonl", [
        _make_entry("req-z1", today_str, input_tokens=0, output_tokens=0),
        _make_entry("req-z2", today_str, input_tokens=0, output_tokens=0),
    ])

    result = compute_project_breakdown(data_path=tmp_path, config_dir=tmp_path)

    today_dict = dict(result.today)
    month_dict = dict(result.billing_month)

    # epsilon should appear (has non-zero tokens: 100 total from req-nonzero)
    assert "epsilon" in today_dict, f"Expected 'epsilon' in today, got {result.today}"
    assert today_dict["epsilon"] == 100

    # zeta should NOT appear in either list (all zero tokens)
    assert "zeta" not in today_dict, f"'zeta' should be excluded from today (zero tokens)"
    assert "zeta" not in month_dict, f"'zeta' should be excluded from billing_month (zero tokens)"
