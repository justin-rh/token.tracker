---
phase: 08-burn-rate-accuracy
reviewed: 2026-05-20T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - monitoring/orchestrator.py
  - ui/session_display.py
  - tests/test_burn_rate.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-05-20
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 8 adds a ring-buffer burn rate computation to `MonitoringOrchestrator` and wires the result
into the session display. The orchestrator logic is sound in structure: strict-increase gating,
billing-cycle reset detection, and a 30-minute window filter are all correct. However there is one
critical bug — the computed `pool_burn_rate_usd_per_hr` value is never forwarded through the
display stack, so the burn rate row can never appear. Two warnings cover an unbounded deque and a
display edge case. Two info items note test coverage gaps.

---

## Critical Issues

### CR-01: `pool_burn_rate_usd_per_hr` is never forwarded to `session_display.py` — feature is dead

**File:** `ui/display_controller.py:226-234` (caller) and `ui/display_controller.py:202-212` (signature)

**Issue:** `cli/main.py` calls `display_controller.create_data_display()` passing `pool_state`,
`web_usage`, `last_web_sync`, and `project_breakdown` — but **not** `pool_burn_rate_usd_per_hr`.
`create_data_display()` itself has no parameter for it, never reads it from `monitoring_data`, and
never inserts it into `processed_data`. As a result `kwargs.get("pool_burn_rate_usd_per_hr")` in
`session_display.py` line 303 always returns `None`, and the burn rate row is permanently
suppressed regardless of how much pool spend data is collected. The orchestrator ring buffer runs
correctly but its output is silently discarded.

**Fix:**

Step 1 — Add the parameter to `create_data_display` in `ui/display_controller.py`:

```python
def create_data_display(
    self,
    data: Dict[str, Any],
    args: Any,
    token_limit: int,
    threshold_state: Optional[ThresholdState] = None,
    pool_state: Optional[PoolState] = None,
    web_usage: Optional[WebUsageData] = None,
    last_web_sync: Optional[datetime] = None,
    project_breakdown: Optional[Any] = None,
    pool_burn_rate_usd_per_hr: Optional[float] = None,   # Phase 8 ADD
) -> RenderableType:
```

Step 2 — Forward it into `processed_data` alongside the other phase kwargs (after line 291):

```python
processed_data["project_breakdown"] = project_breakdown        # Phase 6 NEW
processed_data["pool_burn_rate_usd_per_hr"] = pool_burn_rate_usd_per_hr  # Phase 8 ADD
```

Step 3 — Pass it from `cli/main.py` (after line 234):

```python
renderable = display_controller.create_data_display(
    data,
    args,
    monitoring_data.get("token_limit", token_limit),
    threshold_state=monitoring_data.get("threshold_state"),
    pool_state=monitoring_data.get("pool_state"),
    web_usage=monitoring_data.get("web_usage"),
    last_web_sync=monitoring_data.get("last_web_sync"),
    project_breakdown=monitoring_data.get("project_breakdown"),
    pool_burn_rate_usd_per_hr=monitoring_data.get("pool_burn_rate_usd_per_hr"),  # Phase 8 ADD
)
```

---

## Warnings

### WR-01: Unbounded `deque` grows forever — memory leak over long runtimes

**File:** `monitoring/orchestrator.py:47`

**Issue:** `self._burn_rate_buffer = collections.deque()` has no `maxlen`. The guard at line 232
only appends on strict spend increases, so growth is bounded by the number of pool spend increases
in a billing cycle. In practice this is harmless for typical sessions, but a long-running monitor
instance (days/weeks) with frequent small spend increases could accumulate thousands of entries.
The 30-minute window filter at line 239 trims the *working set* but does not shrink the deque
itself — old entries before the window remain resident.

**Fix:** Set a conservative `maxlen` that bounds entries to a reasonable horizon. At a 10-second
poll interval, 30 minutes of samples is at most 180 entries. A limit of 1 080 covers 3 hours of
continuous spend growth and provides a safety margin without any behavioral change under normal
conditions:

```python
self._burn_rate_buffer: collections.deque = collections.deque(maxlen=1_080)
```

---

### WR-02: `SessionDisplayData.burn_rate` field stale — `format_active_session_screen_v2` path silently drops pool burn rate

**File:** `ui/session_display.py:68` and `ui/session_display.py:134-155`

**Issue:** `SessionDisplayData` carries a `burn_rate: float` field (the old token-burn-rate metric)
and `format_active_session_screen_v2` converts this dataclass to positional/keyword args at line
134-155. The conversion calls `format_active_session_screen` with explicit named parameters —
**none of which include `pool_burn_rate_usd_per_hr`**. Any caller using the v2 dataclass path
cannot pass the pool burn rate through, even after CR-01 is fixed. This creates a silent divergence
between the two call paths.

**Fix:** Add `pool_burn_rate_usd_per_hr: Optional[float] = None` to `SessionDisplayData` and
forward it in `format_active_session_screen_v2`:

```python
@dataclass
class SessionDisplayData:
    ...
    pool_burn_rate_usd_per_hr: Optional[float] = None   # Phase 8 ADD
```

```python
def format_active_session_screen_v2(self, data: SessionDisplayData) -> list[str]:
    return self.format_active_session_screen(
        ...
        pool_burn_rate_usd_per_hr=data.pool_burn_rate_usd_per_hr,  # Phase 8 ADD
    )
```

---

### WR-03: Very small (near-zero) positive burn rates produce astronomically large exhaustion strings

**File:** `ui/session_display.py:306-309`

**Issue:** The guard at line 305 is `if burn_rate_usd_per_hr > 0`, which correctly avoids
`ZeroDivisionError`. However any burn rate between 0 and some small epsilon (e.g., $0.0001/hr)
produces `remaining_hrs` on the order of tens of thousands of hours, and the display renders
something like `~41666h 39m remaining`. This is technically not a crash, but it is a misleading
and user-visible output that will appear during the early warm-up period when only a handful of
very small spend deltas have accumulated in the buffer.

**Fix:** Add a minimum threshold before computing the exhaustion estimate:

```python
_MIN_BURN_RATE_USD_PER_HR = 0.01  # suppress exhaustion estimate below $0.01/hr

if burn_rate_usd_per_hr > _MIN_BURN_RATE_USD_PER_HR:
    remaining_hrs = pool_state.pool_remaining_usd / burn_rate_usd_per_hr
    hours = int(remaining_hrs)
    mins = int((remaining_hrs - hours) * 60)
    exhaust_str = f"~{hours}h {mins}m remaining"
else:
    exhaust_str = "—"
```

---

## Info

### IN-01: `test_burn_rate_computed_from_two_samples` tests the formula but not the 30-minute window filter

**File:** `tests/test_burn_rate.py:32-44`

**Issue:** The test bypasses the actual production cutoff (`t0 - 1800`) by using a 2-hour window
(`t0 - 7200`) in its filter. As written, the test with one sample placed 1 hour ago passes only
because the 2-hour window is wider — but the sample would be *excluded* by the real 30-minute
window used in `orchestrator.py`. This means the 30-minute window boundary itself has zero test
coverage. A sample at exactly `t0 - 1800` (boundary) and one at `t0 - 1801` (just outside) are
not tested.

**Fix:** Add a complementary test that exercises the real 30-minute cutoff:

```python
def test_burn_rate_old_sample_excluded_by_30min_window():
    o = MonitoringOrchestrator()
    t0 = time.time()
    o._burn_rate_buffer.append((t0 - 1801, 0.50))  # just outside 30-min window
    o._burn_rate_buffer.append((t0, 1.50))
    filtered = [s for s in o._burn_rate_buffer if s[0] >= t0 - 1800]
    assert len(filtered) < 2  # oldest sample excluded → no burn rate
```

---

### IN-02: No test for the non-insertion invariant (spend does not increase → buffer not updated)

**File:** `tests/test_burn_rate.py`

**Issue:** The ring buffer's key invariant — that samples are only appended on a strict spend
increase — has no direct test. All four existing tests either start with an empty buffer or
manually append tuples, bypassing the insertion guard at `orchestrator.py:232`. A regression that
removes the `>` check and uses `>=` instead would not be caught.

**Fix:** Add a test that simulates a flat or decreasing spend and verifies the buffer length stays
constant:

```python
def test_no_insertion_when_spend_does_not_increase():
    o = MonitoringOrchestrator()
    o._burn_rate_buffer.append((time.time(), 5.0))
    o._last_burn_sample_spend = 5.0
    # Simulate two cycles with identical spend — should not insert
    initial_len = len(o._burn_rate_buffer)
    for _ in range(3):
        if 5.0 > o._last_burn_sample_spend:
            o._burn_rate_buffer.append((time.time(), 5.0))
            o._last_burn_sample_spend = 5.0
    assert len(o._burn_rate_buffer) == initial_len
```

---

_Reviewed: 2026-05-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
