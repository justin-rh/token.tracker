"""
Unit tests for requestId deduplication in data/reader.py.

Scenario: Claude Code writes multiple JSONL entries per API request during streaming.
The first N-1 entries have input_tokens=1 (placeholder). The final entry has the
true counts. Without dedup, summing all entries inflates counts 100-174x.
"""
import pytest
from data.reader import _deduplicate_entries


def make_entry(request_id, output_tokens, input_tokens=1):
    """Helper: build a minimal JSONL-style entry dict."""
    return {
        "requestId": request_id,
        "message": {
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        }
    }


def test_single_entry_passthrough():
    """A single entry with no duplicates is returned unchanged."""
    entries = [make_entry("req-001", output_tokens=500, input_tokens=800)]
    result = _deduplicate_entries(entries)
    assert len(result) == 1
    assert result[0]["message"]["usage"]["output_tokens"] == 500


def test_duplicates_collapsed_to_highest_output():
    """5 streaming entries for the same request collapse to 1 (the final chunk)."""
    entries = [
        make_entry("req-001", output_tokens=1),    # placeholder
        make_entry("req-001", output_tokens=1),    # placeholder
        make_entry("req-001", output_tokens=50),   # partial
        make_entry("req-001", output_tokens=200),  # partial
        make_entry("req-001", output_tokens=347),  # FINAL — highest
    ]
    result = _deduplicate_entries(entries)
    assert len(result) == 1
    assert result[0]["message"]["usage"]["output_tokens"] == 347


def test_multiple_requests_each_deduplicated():
    """Two different requestIds produce two deduplicated entries."""
    entries = [
        make_entry("req-001", output_tokens=1),
        make_entry("req-001", output_tokens=200),
        make_entry("req-002", output_tokens=1),
        make_entry("req-002", output_tokens=150),
    ]
    result = _deduplicate_entries(entries)
    assert len(result) == 2
    output_tokens = {e["message"]["usage"]["output_tokens"] for e in result}
    assert output_tokens == {200, 150}


def test_entries_without_request_id_preserved():
    """Tool-use result entries (no requestId) are passed through unchanged."""
    entries = [
        {"type": "tool_result", "content": "some result"},   # no requestId
        make_entry("req-001", output_tokens=100),
    ]
    result = _deduplicate_entries(entries)
    assert len(result) == 2
    types = [e.get("type") for e in result]
    assert "tool_result" in types


def test_inflation_ratio():
    """
    Simulates the real-world 100-174x inflation bug.
    10 placeholder entries + 1 final = 11 raw; dedup = 1.
    Token total without dedup = 10*1 + 347 = 357 output tokens total (inflated).
    Token total with dedup = 347 output tokens (correct).
    """
    final_output = 347
    entries = [make_entry("req-001", output_tokens=1)] * 10
    entries.append(make_entry("req-001", output_tokens=final_output))

    raw_total = sum(e["message"]["usage"]["output_tokens"] for e in entries)
    deduped = _deduplicate_entries(entries)
    deduped_total = sum(e["message"]["usage"]["output_tokens"] for e in deduped)

    assert raw_total == 10 + final_output        # 357 — inflated
    assert deduped_total == final_output          # 347 — correct
    assert len(deduped) == 1
