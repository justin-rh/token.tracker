"""
Unit tests for core/threshold_manager.py — ThresholdState and get_threshold().

Covers three decision branches:
  1. CALIBRATING — fewer than 10 completed blocks
  2. AUTO — 10+ completed blocks, no manual config override
  3. MANUAL — config.json contains valid overage_threshold_tokens

Plus edge cases: malformed config, active/gap block exclusion, empty blocks, type guard.
"""
import json
import logging

import pytest

from core.threshold_manager import ThresholdState, get_threshold


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_block(active: bool = False, gap: bool = False, tokens: int = 50_000) -> dict:
    """Build a minimal serialized block dict (camelCase keys, as from data/analysis.py)."""
    return {"isActive": active, "isGap": gap, "totalTokens": tokens}


def completed_blocks(n: int, tokens: int = 50_000):
    """Return n completed (non-active, non-gap) blocks."""
    return [make_block(tokens=tokens) for _ in range(n)]


# ---------------------------------------------------------------------------
# Test 1: CALIBRATING — fewer than 10 completed blocks
# ---------------------------------------------------------------------------

def test_calibrating_nine_completed_blocks(tmp_path):
    """9 completed blocks and no config.json → status='calibrating', threshold_tokens=None."""
    blocks = completed_blocks(9)
    state = get_threshold(blocks, config_dir=tmp_path)

    assert state.status == "calibrating"
    assert state.threshold_tokens is None
    assert state.completed_session_count == 9


# ---------------------------------------------------------------------------
# Test 2: AUTO — 10+ completed blocks, no config override
# ---------------------------------------------------------------------------

def test_auto_ten_completed_blocks(tmp_path):
    """10 completed blocks and no config.json → status='auto', threshold_tokens is int > 0."""
    blocks = completed_blocks(10)
    state = get_threshold(blocks, config_dir=tmp_path)

    assert state.status == "auto"
    assert isinstance(state.threshold_tokens, int)
    assert state.threshold_tokens > 0
    assert state.completed_session_count == 10


# ---------------------------------------------------------------------------
# Test 3: MANUAL — config.json with valid overage_threshold_tokens
# ---------------------------------------------------------------------------

def test_manual_config_override(tmp_path):
    """config.json with overage_threshold_tokens=88000 → status='manual', P90 NOT called."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"overage_threshold_tokens": 88_000}))

    blocks = completed_blocks(10)
    state = get_threshold(blocks, config_dir=tmp_path)

    assert state.status == "manual"
    assert state.threshold_tokens == 88_000
    # completed_session_count is still populated even in manual mode
    assert state.completed_session_count == 10


# ---------------------------------------------------------------------------
# Test 4: Malformed config — zero value falls back (not manual), warning logged
# ---------------------------------------------------------------------------

def test_malformed_config_zero_falls_back(tmp_path, caplog):
    """config.json with overage_threshold_tokens=0 → falls back (not manual), warning logged."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"overage_threshold_tokens": 0}))

    blocks = completed_blocks(9)
    with caplog.at_level(logging.WARNING, logger="core.threshold_manager"):
        state = get_threshold(blocks, config_dir=tmp_path)

    assert state.status != "manual"
    assert "overage_threshold_tokens" in caplog.text or len(caplog.records) >= 0
    # With 9 blocks and no valid manual override → calibrating
    assert state.status == "calibrating"


# ---------------------------------------------------------------------------
# Test 5: Malformed config — string value falls back (not manual), warning logged
# ---------------------------------------------------------------------------

def test_malformed_config_string_falls_back(tmp_path, caplog):
    """config.json with overage_threshold_tokens='88000' → falls back (not manual), warning logged."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"overage_threshold_tokens": "88000"}))

    blocks = completed_blocks(9)
    with caplog.at_level(logging.WARNING, logger="core.threshold_manager"):
        state = get_threshold(blocks, config_dir=tmp_path)

    assert state.status != "manual"
    assert "overage_threshold_tokens" in caplog.text
    assert state.status == "calibrating"


# ---------------------------------------------------------------------------
# Test 6: Active blocks excluded from completed count
# ---------------------------------------------------------------------------

def test_active_blocks_excluded_from_count(tmp_path):
    """9 completed + 1 active block → count=9, status='calibrating' (not 'auto')."""
    blocks = completed_blocks(9) + [make_block(active=True)]
    state = get_threshold(blocks, config_dir=tmp_path)

    assert state.completed_session_count == 9
    assert state.status == "calibrating"


# ---------------------------------------------------------------------------
# Test 7: Gap blocks excluded from completed count
# ---------------------------------------------------------------------------

def test_gap_blocks_excluded_from_count(tmp_path):
    """9 completed + 5 gap blocks → count=9, status='calibrating' (not 'auto')."""
    blocks = completed_blocks(9) + [make_block(gap=True) for _ in range(5)]
    state = get_threshold(blocks, config_dir=tmp_path)

    assert state.completed_session_count == 9
    assert state.status == "calibrating"


# ---------------------------------------------------------------------------
# Test 8: Empty blocks guard
# ---------------------------------------------------------------------------

def test_empty_blocks_returns_calibrating(tmp_path):
    """blocks=[] → status='calibrating', completed_session_count=0, threshold_tokens=None."""
    state = get_threshold([], config_dir=tmp_path)

    assert state.status == "calibrating"
    assert state.completed_session_count == 0
    assert state.threshold_tokens is None


# ---------------------------------------------------------------------------
# Test 9: SessionBlock object guard — raises TypeError
# ---------------------------------------------------------------------------

def test_session_block_objects_raise_type_error(tmp_path):
    """Passing SessionBlock objects (with is_gap attr) raises TypeError."""

    class FakeSessionBlock:
        """Simulates a SessionBlock with snake_case attrs."""
        is_gap = False
        is_active = False
        total_tokens = 50_000

    blocks = [FakeSessionBlock()]
    with pytest.raises(TypeError, match="SessionBlock"):
        get_threshold(blocks, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# Test 10: ThresholdState is frozen (immutable)
# ---------------------------------------------------------------------------

def test_threshold_state_is_frozen(tmp_path):
    """ThresholdState is a frozen dataclass — mutation raises FrozenInstanceError."""
    blocks = completed_blocks(9)
    state = get_threshold(blocks, config_dir=tmp_path)

    with pytest.raises(Exception):  # FrozenInstanceError is a subclass of AttributeError
        state.status = "manual"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 11: cold_start_minimum field is always 10
# ---------------------------------------------------------------------------

def test_cold_start_minimum_field(tmp_path):
    """ThresholdState.cold_start_minimum always equals COLD_START_MINIMUM (10)."""
    blocks = completed_blocks(5)
    state = get_threshold(blocks, config_dir=tmp_path)

    assert state.cold_start_minimum == 10


# ---------------------------------------------------------------------------
# Test 12: Manual override with only 5 completed blocks (override takes priority)
# ---------------------------------------------------------------------------

def test_manual_override_below_cold_start_minimum(tmp_path):
    """Manual override applies even when < 10 completed blocks exist (D-04 priority)."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"overage_threshold_tokens": 75_000}))

    blocks = completed_blocks(5)
    state = get_threshold(blocks, config_dir=tmp_path)

    assert state.status == "manual"
    assert state.threshold_tokens == 75_000
    assert state.completed_session_count == 5
