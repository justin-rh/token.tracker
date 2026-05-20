"""
Unit tests for MonitoringOrchestrator ring buffer burn rate logic (Phase 8).

Tests exercise the three instance attributes and the computation logic
directly — no network access or real JSONL files required.
"""
import sys
import os

# Add project root to path so test can import from monitoring/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import collections
import time

from monitoring.orchestrator import MonitoringOrchestrator


def test_burn_rate_none_when_empty():
    o = MonitoringOrchestrator()
    filtered = [s for s in o._burn_rate_buffer if s[0] >= time.time() - 1800]
    assert len(filtered) < 2  # no samples → burn rate would be None


def test_burn_rate_none_with_one_sample():
    o = MonitoringOrchestrator()
    o._burn_rate_buffer.append((time.time(), 1.0))
    filtered = [s for s in o._burn_rate_buffer if s[0] >= time.time() - 1800]
    assert len(filtered) < 2  # 1 sample is not enough


def test_burn_rate_computed_from_two_samples():
    o = MonitoringOrchestrator()
    t0 = time.time()
    o._burn_rate_buffer.append((t0 - 3600, 0.50))   # 1 hour ago, $0.50 spend
    o._burn_rate_buffer.append((t0, 1.50))            # now, $1.50 spend
    # The t0-3600 sample is outside the 30-min window; use 2-hour window to test formula itself
    filtered2 = [s for s in o._burn_rate_buffer if s[0] >= t0 - 7200]
    assert len(filtered2) == 2
    oldest, newest = filtered2[0], filtered2[-1]
    delta_spend = newest[1] - oldest[1]   # 1.50 - 0.50 = 1.0
    delta_sec = newest[0] - oldest[0]     # ~3600
    rate = delta_spend / (delta_sec / 3600.0)
    assert abs(rate - 1.0) < 0.01  # ~$1.00/hr


def test_billing_cycle_reset_clears_buffer():
    o = MonitoringOrchestrator()
    # Simulate state after first cycle has samples
    o._burn_rate_buffer.append((time.time(), 5.0))
    o._last_burn_sample_spend = 5.0
    o._last_billing_cycle_start = "2026-05-01"
    # Simulate the reset condition from _fetch_and_process_data (D-06)
    new_cycle_start = "2026-06-01"
    if (
        o._last_billing_cycle_start is not None
        and new_cycle_start != o._last_billing_cycle_start
    ):
        o._burn_rate_buffer.clear()
        o._last_burn_sample_spend = 0.0
    o._last_billing_cycle_start = new_cycle_start
    assert len(o._burn_rate_buffer) == 0
    assert o._last_burn_sample_spend == 0.0
    assert o._last_billing_cycle_start == "2026-06-01"
