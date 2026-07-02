"""
Unit tests for core/pool_state_manager.py — PoolState and compute_pool_state().

Covers all decision branches D-01 through D-10:
  - D-01: Only completed (non-active, non-gap) sessions in billing period are counted
  - D-02: OVERAGE classification: totalTokens > threshold_tokens
  - D-03: Pool spend recomputed from blocks on each refresh
  - D-04: pool_spend.json written atomically on each compute_pool_state() call
  - D-05/D-06: billing_cycle_start from config.json + stale cache detection
  - D-07/D-08: pool_size_usd and billing_cycle_start_day from config.json with defaults
  - D-09/D-10: pool_pct_spent and pool_remaining_usd derived from pool_spend/pool_size

Calibration state (threshold_tokens=None) must return pool_spend_usd=0.0 without TypeError.
"""
import json
import logging
from datetime import date, timedelta

import pytest

from core.pool_state_manager import PoolState, compute_pool_state
from core.threshold_manager import ThresholdState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_block(
    active: bool = False,
    gap: bool = False,
    tokens: int = 50_000,
    cost: float = 0.10,
    start_time: str = "2026-05-08T10:00:00",
) -> dict:
    """Build a minimal serialized block dict (camelCase keys, as from data/analysis.py)."""
    return {
        "isActive": active,
        "isGap": gap,
        "totalTokens": tokens,
        "costUSD": cost,
        "startTime": start_time,
    }


# Shared threshold states used across tests
CALIBRATING_STATE = ThresholdState(
    status="calibrating",
    threshold_tokens=None,
    completed_session_count=5,
)

KNOWN_STATE = ThresholdState(
    status="auto",
    threshold_tokens=88_000,
    completed_session_count=15,
)


# ---------------------------------------------------------------------------
# Test 1: Calibrating state — no TypeError, pool_spend=0.0
# ---------------------------------------------------------------------------

def test_calibrating_returns_zero_spend(tmp_path):
    """threshold_state.threshold_tokens is None → pool_spend_usd=0.0, no TypeError."""
    blocks = [make_block(tokens=100_000, cost=1.50)]
    result = compute_pool_state(blocks, CALIBRATING_STATE, config_dir=tmp_path)

    assert result.pool_spend_usd == 0.0
    assert result.is_overage is False


# ---------------------------------------------------------------------------
# Test 2: INCLUDED session — excluded from pool spend
# ---------------------------------------------------------------------------

def test_included_session_excluded_from_spend(tmp_path):
    """totalTokens=50_000 < threshold=88_000 → INCLUDED → pool_spend_usd=0.0."""
    blocks = [make_block(tokens=50_000, cost=0.75)]
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    assert result.pool_spend_usd == 0.0


# ---------------------------------------------------------------------------
# Test 3: OVERAGE session — counted in pool spend
# ---------------------------------------------------------------------------

def test_overage_session_counted_in_spend(tmp_path):
    """totalTokens=100_000 > threshold=88_000 → OVERAGE → pool_spend_usd=1.50."""
    blocks = [make_block(tokens=100_000, cost=1.50)]
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 5, 8))

    assert result.pool_spend_usd == pytest.approx(1.50)


# ---------------------------------------------------------------------------
# Test 4: Multiple OVERAGE sessions — costs summed; INCLUDED excluded
# ---------------------------------------------------------------------------

def test_multiple_overage_sessions_summed(tmp_path):
    """Three blocks: two OVERAGE (costs 1.0, 2.0), one INCLUDED (cost 0.50) → pool_spend=3.0."""
    blocks = [
        make_block(tokens=100_000, cost=1.0),   # OVERAGE
        make_block(tokens=200_000, cost=2.0),   # OVERAGE
        make_block(tokens=50_000, cost=0.50),   # INCLUDED
    ]
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 5, 8))

    assert result.pool_spend_usd == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Test 5: Active block — included in pool spend (real-time bar update)
# ---------------------------------------------------------------------------

def test_active_block_included(tmp_path):
    """Active block with OVERAGE token count → pool_spend_usd includes cost (real-time)."""
    blocks = [make_block(active=True, tokens=100_000, cost=1.50)]
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 5, 8))

    assert result.pool_spend_usd == pytest.approx(1.50)


# ---------------------------------------------------------------------------
# Test 6: Gap block — excluded (D-01: only completed sessions)
# ---------------------------------------------------------------------------

def test_gap_block_excluded(tmp_path):
    """Gap block with OVERAGE token count → pool_spend_usd=0.0 (gap excluded)."""
    blocks = [make_block(gap=True, tokens=100_000, cost=1.50)]
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    assert result.pool_spend_usd == 0.0


# ---------------------------------------------------------------------------
# Test 7: Billing period filter — old sessions excluded
# ---------------------------------------------------------------------------

def test_billing_period_filter_excludes_old_sessions(tmp_path):
    """Block from before current billing cycle excluded; in-period block counted."""
    # Use a fixed today=2026-05-15 with default cycle_day=1 → billing_start=2026-05-01
    old_date = "2026-03-01T10:00:00"      # before billing_start → excluded
    in_period = "2026-05-15T10:00:00"     # on today → included

    blocks = [
        make_block(tokens=100_000, cost=1.50, start_time=old_date),
        make_block(tokens=100_000, cost=2.00, start_time=in_period),
    ]
    result = compute_pool_state(
        blocks, KNOWN_STATE, config_dir=tmp_path,
        today=date(2026, 5, 15),
    )

    # Only the in-period block should be counted
    assert result.pool_spend_usd == pytest.approx(2.00)


# ---------------------------------------------------------------------------
# Test 8: pool_size_usd from config.json
# ---------------------------------------------------------------------------

def test_pool_size_from_config(tmp_path):
    """config.json with pool_size_usd=300.0 → result.pool_size_usd==300.0."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"pool_size_usd": 300.0}))

    blocks = []
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    assert result.pool_size_usd == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# Test 9: billing_cycle_start_day from config.json
# ---------------------------------------------------------------------------

def test_billing_cycle_start_day_from_config(tmp_path):
    """config.json with billing_cycle_start_day=15 → billing_cycle_start has day=15 (or adjusted)."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"billing_cycle_start_day": 15}))

    blocks = []
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    cycle_start = date.fromisoformat(result.billing_cycle_start)
    assert cycle_start.day == 15


# ---------------------------------------------------------------------------
# Test 10: Malformed pool_size_usd — warning logged, default used
# ---------------------------------------------------------------------------

def test_malformed_pool_size_logs_warning_and_uses_default(tmp_path, caplog):
    """config.json with pool_size_usd='bad' → WARNING containing 'pool_size_usd', default 500.0."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"pool_size_usd": "bad"}))

    blocks = []
    with caplog.at_level(logging.WARNING, logger="core.pool_state_manager"):
        result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    assert "pool_size_usd" in caplog.text
    assert result.pool_size_usd == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Test 11: Malformed billing_cycle_start_day — warning logged, default used (day=1)
# ---------------------------------------------------------------------------

def test_malformed_cycle_day_logs_warning_and_uses_default(tmp_path, caplog):
    """config.json with billing_cycle_start_day=99 → WARNING, billing_cycle_start has day=1."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"billing_cycle_start_day": 99}))

    blocks = []
    with caplog.at_level(logging.WARNING, logger="core.pool_state_manager"):
        result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    assert "billing_cycle_start_day" in caplog.text
    cycle_start = date.fromisoformat(result.billing_cycle_start)
    assert cycle_start.day == 1


# ---------------------------------------------------------------------------
# Test 12: pool_spend.json written atomically after compute_pool_state()
# ---------------------------------------------------------------------------

def test_pool_spend_cache_written_atomically(tmp_path):
    """After compute_pool_state(), pool_spend.json exists with required keys."""
    blocks = [make_block(tokens=100_000, cost=1.50)]
    compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    cache_file = tmp_path / "pool_spend.json"
    assert cache_file.exists(), "pool_spend.json must be written after compute_pool_state()"

    with open(cache_file, encoding="utf-8") as f:
        data = json.load(f)

    assert "pool_spend_usd" in data
    assert "billing_cycle_start" in data
    assert "last_updated" in data


# ---------------------------------------------------------------------------
# Test 13: PoolState is frozen (immutable)
# ---------------------------------------------------------------------------

def test_pool_state_is_frozen(tmp_path):
    """PoolState is a frozen dataclass — mutation raises FrozenInstanceError (AttributeError subclass)."""
    blocks = []
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    with pytest.raises(AttributeError):  # FrozenInstanceError is a subclass of AttributeError
        result.pool_spend_usd = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 14: pool_pct_spent and pool_remaining_usd calculations
# ---------------------------------------------------------------------------

def test_pool_pct_spent_calculation(tmp_path):
    """pool_spend=100.0, pool_size=500.0 → pool_pct_spent==20.0, pool_remaining_usd==400.0."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"pool_size_usd": 500.0}))

    # Create OVERAGE blocks summing to exactly 100.0
    blocks = [make_block(tokens=100_000, cost=100.0)]
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 5, 8))

    assert result.pool_spend_usd == pytest.approx(100.0)
    assert result.pool_size_usd == pytest.approx(500.0)
    assert result.pool_pct_spent == pytest.approx(20.0)
    assert result.pool_remaining_usd == pytest.approx(400.0)


# ---------------------------------------------------------------------------
# Test 15: Seed USD added to computed OVERAGE spend
# ---------------------------------------------------------------------------

def test_seed_usd_added_to_computed_spend(tmp_path):
    """Seed of $47.23 plus one OVERAGE session of $5.00 → pool_spend_usd==52.23."""
    today = date.today().isoformat()
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "pool_spend_seed_usd": 47.23,
        "pool_spend_seed_date": today,
    }))

    blocks = [make_block(tokens=100_000, cost=5.00, start_time=today + "T15:00:00")]
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    assert result.pool_spend_usd == pytest.approx(52.23)


# ---------------------------------------------------------------------------
# Test 16: seed_date excludes pre-seed sessions from log computation
# ---------------------------------------------------------------------------

def test_seed_date_excludes_pre_seed_sessions(tmp_path):
    """Sessions before seed_date are covered by the seed — not double-counted from logs."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "pool_spend_seed_usd": 20.00,
        "pool_spend_seed_date": today,
    }))

    # Yesterday's OVERAGE session — should be excluded (covered by seed)
    blocks = [make_block(tokens=100_000, cost=10.00, start_time=yesterday + "T10:00:00")]
    result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    # Only seed contributes — yesterday's session is excluded
    assert result.pool_spend_usd == pytest.approx(20.00)


# ---------------------------------------------------------------------------
# Test 17: Malformed seed_usd — warning logged, default 0.0 used
# ---------------------------------------------------------------------------

def test_malformed_seed_usd_logs_warning_and_uses_default(tmp_path, caplog):
    """pool_spend_seed_usd='bad' → WARNING, seed treated as 0.0."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"pool_spend_seed_usd": "bad"}))

    blocks = []
    with caplog.at_level(logging.WARNING, logger="core.pool_state_manager"):
        result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path)

    assert "pool_spend_seed_usd" in caplog.text
    assert result.pool_spend_usd == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Test 18: previous-month branch via injected today date
# ---------------------------------------------------------------------------

def test_billing_cycle_start_previous_month(tmp_path):
    """today.day < cycle_day → billing_start rolls back to previous month."""
    # today=2026-01-15, cycle_day=20 → today.day (15) < cycle_day (20) → prev month
    # 2026-01-15 prev month with day=20 → 2025-12-20
    config_file = tmp_path / "config.json"
    config_file.write_text('{"billing_cycle_start_day": 20}')
    result = compute_pool_state(
        [], KNOWN_STATE, config_dir=tmp_path,
        today=date(2026, 1, 15),
    )
    cycle_start = date.fromisoformat(result.billing_cycle_start)
    assert cycle_start == date(2025, 12, 20), f"Expected 2025-12-20, got {cycle_start}"


# ---------------------------------------------------------------------------
# Test 19: exact-match branch (today.day == cycle_day)
# ---------------------------------------------------------------------------

def test_billing_cycle_start_exact_match_day(tmp_path):
    """today.day == cycle_day → billing_start is today with day replaced."""
    # today=2026-03-01, cycle_day=1 → today.day (1) >= cycle_day (1) → same month
    config_file = tmp_path / "config.json"
    config_file.write_text('{"billing_cycle_start_day": 1}')
    result = compute_pool_state(
        [], KNOWN_STATE, config_dir=tmp_path,
        today=date(2026, 3, 1),
    )
    cycle_start = date.fromisoformat(result.billing_cycle_start)
    assert cycle_start == date(2026, 3, 1), f"Expected 2026-03-01, got {cycle_start}"


# ---------------------------------------------------------------------------
# Phase 10: daily_pool_spend tests (ANLX-01, ANLX-03)
# ---------------------------------------------------------------------------

class TestDailyPoolSpend:
    """daily_pool_spend tuple covers all days; only overage blocks contribute."""

    def test_no_overage_blocks_empty_spend(self, tmp_path):
        """All blocks below threshold → all daily spend values are 0.0."""
        blocks = [make_block(tokens=10_000, cost=0.05, start_time="2026-06-01T10:00:00")]
        result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 6, 2))
        assert all(spend == 0.0 for _, spend in result.daily_pool_spend)
        # Covers 2 days: Jun 01 and Jun 02
        assert len(result.daily_pool_spend) == 2

    def test_single_overage_block_buckets_to_correct_date(self, tmp_path):
        """A single overage block is bucketed to its start date."""
        blocks = [make_block(tokens=200_000, cost=1.50, start_time="2026-06-01T14:30:00")]
        result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 6, 1))
        assert len(result.daily_pool_spend) == 1
        date_str, spend = result.daily_pool_spend[0]
        assert date_str == "2026-06-01"
        assert abs(spend - 1.50) < 0.001

    def test_multi_day_spend_bucketed_correctly(self, tmp_path):
        """Overage blocks on different days are bucketed independently."""
        blocks = [
            make_block(tokens=200_000, cost=2.00, start_time="2026-06-01T09:00:00"),
            make_block(tokens=150_000, cost=1.00, start_time="2026-06-02T11:00:00"),
            make_block(tokens=300_000, cost=3.50, start_time="2026-06-02T15:00:00"),
        ]
        result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 6, 2))
        spend_map = dict(result.daily_pool_spend)
        assert abs(spend_map["2026-06-01"] - 2.00) < 0.001
        assert abs(spend_map["2026-06-02"] - 4.50) < 0.001

    def test_full_day_range_includes_zero_days(self, tmp_path):
        """daily_pool_spend covers every day from billing_cycle_start to today, gaps filled with 0.0."""
        blocks = [make_block(tokens=200_000, cost=1.00, start_time="2026-06-01T10:00:00")]
        result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 6, 3))
        spend_map = dict(result.daily_pool_spend)
        assert spend_map["2026-06-01"] > 0
        assert spend_map["2026-06-02"] == 0.0
        assert spend_map["2026-06-03"] == 0.0
        assert len(result.daily_pool_spend) == 3

    def test_calibrating_state_all_zero(self, tmp_path):
        """When calibrating (threshold_tokens=None), all daily spend values are 0.0."""
        blocks = [make_block(tokens=200_000, cost=1.00, start_time="2026-06-01T10:00:00")]
        result = compute_pool_state(blocks, CALIBRATING_STATE, config_dir=tmp_path, today=date(2026, 6, 1))
        assert all(spend == 0.0 for _, spend in result.daily_pool_spend)

    def test_gap_blocks_excluded_from_daily_spend(self, tmp_path):
        """Gap blocks are not bucketed into daily spend."""
        blocks = [
            make_block(gap=True, tokens=200_000, cost=5.00, start_time="2026-06-01T10:00:00"),
            make_block(tokens=200_000, cost=1.00, start_time="2026-06-01T12:00:00"),
        ]
        result = compute_pool_state(blocks, KNOWN_STATE, config_dir=tmp_path, today=date(2026, 6, 1))
        spend_map = dict(result.daily_pool_spend)
        assert abs(spend_map["2026-06-01"] - 1.00) < 0.001


# ---------------------------------------------------------------------------
# read_pool_size / write_pool_size — tray "Max Pool" menu support
# ---------------------------------------------------------------------------

class TestPoolSizeReadWrite:
    """read_pool_size() and write_pool_size() round-trip through config.json."""

    def test_read_default_when_no_config(self, tmp_path):
        from core.pool_state_manager import read_pool_size
        assert read_pool_size(config_dir=tmp_path) == pytest.approx(500.0)

    def test_write_then_read_round_trip(self, tmp_path):
        from core.pool_state_manager import read_pool_size, write_pool_size
        write_pool_size(750.0, config_dir=tmp_path)
        assert read_pool_size(config_dir=tmp_path) == pytest.approx(750.0)

    def test_write_preserves_other_config_keys(self, tmp_path):
        from core.pool_state_manager import write_pool_size
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"pool_size_usd": 500.0, "billing_cycle_start_day": 15})
        )
        write_pool_size(1000.0, config_dir=tmp_path)
        data = json.loads(config_file.read_text())
        assert data["pool_size_usd"] == pytest.approx(1000.0)
        assert data["billing_cycle_start_day"] == 15

    def test_write_creates_config_dir(self, tmp_path):
        from core.pool_state_manager import read_pool_size, write_pool_size
        nested = tmp_path / "does-not-exist-yet"
        write_pool_size(750.0, config_dir=nested)
        assert read_pool_size(config_dir=nested) == pytest.approx(750.0)

    def test_new_size_flows_into_compute_pool_state(self, tmp_path):
        from core.pool_state_manager import write_pool_size
        write_pool_size(1000.0, config_dir=tmp_path)
        result = compute_pool_state([], KNOWN_STATE, config_dir=tmp_path)
        assert result.pool_size_usd == pytest.approx(1000.0)
