"""Orchestrator for monitoring components."""

import collections
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from claude_monitor.core.plans import DEFAULT_TOKEN_LIMIT, get_token_limit
from claude_monitor.core.threshold_manager import ThresholdState, get_threshold
from claude_monitor.core.pool_state_manager import PoolState, compute_pool_state
from claude_monitor.core.project_breakdown import compute_project_breakdown
from claude_monitor.error_handling import report_error
from claude_monitor.monitoring.data_manager import DataManager
from claude_monitor.monitoring.session_monitor import SessionMonitor

logger = logging.getLogger(__name__)


class MonitoringOrchestrator:
    """Orchestrates monitoring components following SRP."""

    def __init__(
        self, update_interval: int = 10, data_path: Optional[str] = None
    ) -> None:
        """Initialize orchestrator with components.

        Args:
            update_interval: Seconds between updates when the window is visible.
            data_path: Optional path to Claude data directory
        """
        self.update_interval: int = update_interval
        self.background_interval: int = 60  # seconds between updates when window is hidden

        self.data_manager: DataManager = DataManager(cache_ttl=5, hours_back=720, data_path=data_path)
        self.session_monitor: SessionMonitor = SessionMonitor()

        self._monitoring: bool = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._update_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._last_valid_data: Optional[Dict[str, Any]] = None
        self._args: Optional[Any] = None
        self._web_poller: Optional[Any] = None  # Phase 4: WebPoller instance (Any avoids circular import)
        self._first_data_event: threading.Event = threading.Event()
        self._visibility_check: Optional[Callable[[], bool]] = None  # returns True when window is visible

        # Phase 8: rolling ring buffer for pool burn rate computation (D-01..D-06, 08-CONTEXT.md)
        self._burn_rate_buffer: collections.deque = collections.deque()  # stores (timestamp: float, pool_spend_usd: float) tuples
        self._last_burn_sample_spend: float = 0.0   # last pool_spend_usd value inserted into buffer
        self._last_billing_cycle_start: Optional[str] = None  # detect billing cycle resets (D-06)

    def start(self) -> None:
        """Start monitoring."""
        if self._monitoring:
            logger.warning("Monitoring already running")
            return

        logger.info(f"Starting monitoring with {self.update_interval}s interval")
        self._monitoring = True
        self._stop_event.clear()

        # Start monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop, name="MonitoringThread", daemon=True
        )
        self._monitor_thread.start()

    def stop(self) -> None:
        """Stop monitoring."""
        if not self._monitoring:
            return

        logger.info("Stopping monitoring")
        self._monitoring = False
        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

        self._monitor_thread = None
        self._first_data_event.clear()

    def set_args(self, args: Any) -> None:
        """Set command line arguments for token limit calculation.

        Args:
            args: Command line arguments
        """
        self._args = args

    def set_visibility_check(self, check: Callable[[], bool]) -> None:
        """Register a callable that returns True when the console window is visible.

        When the window is hidden the monitoring loop sleeps for background_interval
        (default 60 s) instead of update_interval (default 10 s). The loop wakes
        within 1 s of the window being restored so the display refreshes immediately.
        """
        self._visibility_check = check

    def set_web_poller(self, poller: Any) -> None:
        """Register the WebPoller instance for web usage data retrieval.

        Called from cli/main.py after WebPoller.start(). The poller's
        get_web_usage() is called on every monitoring cycle in _fetch_and_process_data().
        Per D-14 (04-CONTEXT.md).

        Args:
            poller: WebPoller instance (typed as Any to avoid circular import)
        """
        self._web_poller = poller

    def register_update_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register callback for data updates.

        Args:
            callback: Function to call with monitoring data
        """
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)
            logger.debug("Registered update callback")

    def register_session_callback(
        self, callback: Callable[[str, str, Optional[Dict[str, Any]]], None]
    ) -> None:
        """Register callback for session changes.

        Args:
            callback: Function(event_type, session_id, session_data)
        """
        self.session_monitor.register_callback(callback)

    def force_refresh(self) -> Optional[Dict[str, Any]]:
        """Force immediate data refresh.

        Returns:
            Fresh data or None if fetch fails
        """
        return self._fetch_and_process_data(force_refresh=True)

    def wait_for_initial_data(self, timeout: float = 10.0) -> bool:
        """Wait for initial data to be fetched.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if data was received, False if timeout
        """
        return self._first_data_event.wait(timeout=timeout)

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Monitoring loop started")

        # Initial fetch
        self._fetch_and_process_data()

        while self._monitoring:
            visible = self._visibility_check() if self._visibility_check else True

            if visible:
                # Window visible: single wait — no extra thread wakeups that
                # would contend with Rich's auto-refresh and cause display flicker.
                if self._stop_event.wait(timeout=self.update_interval):
                    if not self._monitoring:
                        break
            else:
                # Window hidden: 1-second ticks so restore is detected quickly
                # and triggers an immediate refresh when the user brings it back.
                slept = 0
                while slept < self.background_interval and self._monitoring:
                    if self._stop_event.wait(timeout=1.0):
                        break
                    slept += 1
                    if self._visibility_check and self._visibility_check():
                        logger.debug("Window restored — triggering immediate refresh")
                        break
                if not self._monitoring:
                    break

            self._fetch_and_process_data()

        logger.info("Monitoring loop ended")

    def _fetch_and_process_data(
        self, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Fetch data and notify callbacks.

        Args:
            force_refresh: Force cache refresh

        Returns:
            Processed data or None if failed
        """
        try:
            # Fetch data
            start_time: float = time.time()
            data: Optional[Dict[str, Any]] = self.data_manager.get_data(
                force_refresh=force_refresh
            )

            if data is None:
                logger.warning("No data fetched")
                return None

            # Validate and update session tracking
            is_valid: bool
            errors: List[str]
            is_valid, errors = self.session_monitor.update(data)
            if not is_valid:
                logger.error(f"Data validation failed: {errors}")
                return None

            # Calculate token limit
            token_limit: int = self._calculate_token_limit(data)

            # Phase 2: compute threshold state (cold-start / P90 auto / manual override)
            # Only runs for custom plan; other plans have static limits with no P90 calibration.
            blocks: List[Any] = data.get("blocks", [])
            if getattr(self._args, "plan", "pro") == "custom":
                threshold_state: ThresholdState = get_threshold(blocks)
                # D-pitfall-5: keep token_limit as int for backward compat with progress bar math.
                # During calibration, use DEFAULT_TOKEN_LIMIT so percentage calculations don't
                # divide by zero or show misleading values. For auto/manual, use the real threshold.
                if threshold_state.status == "calibrating":
                    token_limit = DEFAULT_TOKEN_LIMIT
                elif threshold_state.threshold_tokens is not None:
                    token_limit = threshold_state.threshold_tokens
            else:
                threshold_state = None

            # Phase 3: compute pool state (pool spend, billing period, persistence)
            pool_state: PoolState = compute_pool_state(blocks, threshold_state)

            # Phase 6: compute per-project token breakdown from local JSONL files
            project_breakdown = compute_project_breakdown()

            # Phase 8: ring buffer burn rate update (D-01..D-09, 08-CONTEXT.md)
            # Step 1 — billing cycle reset detection (D-06)
            if (
                self._last_billing_cycle_start is not None
                and pool_state.billing_cycle_start != self._last_billing_cycle_start
            ):
                logger.info(
                    "Burn rate buffer cleared — billing cycle reset detected "
                    "(old=%s, new=%s)",
                    self._last_billing_cycle_start,
                    pool_state.billing_cycle_start,
                )
                self._burn_rate_buffer.clear()
                self._last_burn_sample_spend = 0.0
            self._last_billing_cycle_start = pool_state.billing_cycle_start

            # Step 2 — sample insertion on spend increase (D-05)
            if pool_state.pool_spend_usd > self._last_burn_sample_spend:
                self._burn_rate_buffer.append((time.time(), pool_state.pool_spend_usd))
                self._last_burn_sample_spend = pool_state.pool_spend_usd

            # Step 3 — compute burn rate from 30-min window (D-07, D-08)
            _now = time.time()
            _cutoff = _now - 1800.0
            _filtered = [s for s in self._burn_rate_buffer if s[0] >= _cutoff]
            if len(_filtered) >= 2:
                _oldest, _newest = _filtered[0], _filtered[-1]
                _delta_spend = _newest[1] - _oldest[1]
                _delta_sec = _newest[0] - _oldest[0]
                burn_rate_usd_per_hr: Optional[float] = (
                    _delta_spend / (_delta_sec / 3600.0) if _delta_sec > 0 else None
                )
            else:
                burn_rate_usd_per_hr = None

            # Prepare monitoring data
            monitoring_data: Dict[str, Any] = {
                "data": data,
                "token_limit": token_limit,           # int — kept for backward compat
                "threshold_state": threshold_state,   # ThresholdState | None — new in Phase 2
                "pool_state": pool_state,              # Phase 3 NEW
                "pool_burn_rate_usd_per_hr": burn_rate_usd_per_hr,  # Phase 8 NEW
                "project_breakdown": project_breakdown,  # Phase 6 NEW
                "web_usage": self._web_poller.get_web_usage() if self._web_poller else None,  # Phase 4 NEW
                "last_web_sync": self._web_poller.get_last_sync_time() if self._web_poller else None,  # Phase 4 NEW
                "args": self._args,
                "session_id": self.session_monitor.current_session_id,
                "session_count": self.session_monitor.session_count,
            }

            # Store last valid data
            self._last_valid_data = monitoring_data

            # Signal that first data has been received
            if not self._first_data_event.is_set():
                self._first_data_event.set()

            # Notify callbacks
            for callback in self._update_callbacks:
                try:
                    callback(monitoring_data)
                except Exception as e:
                    logger.error(f"Callback error: {e}", exc_info=True)
                    report_error(
                        exception=e,
                        component="orchestrator",
                        context_name="callback_error",
                    )

            elapsed: float = time.time() - start_time
            logger.debug(f"Data processing completed in {elapsed:.3f}s")

            return monitoring_data

        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}", exc_info=True)
            report_error(
                exception=e, component="orchestrator", context_name="monitoring_cycle"
            )
            return None

    def _calculate_token_limit(self, data: Dict[str, Any]) -> int:
        """Calculate token limit based on plan and data.

        Args:
            data: Monitoring data

        Returns:
            Token limit
        """
        if not self._args:
            return DEFAULT_TOKEN_LIMIT

        plan: str = getattr(self._args, "plan", "pro")

        try:
            if plan == "custom":
                blocks: List[Any] = data.get("blocks", [])
                return get_token_limit(plan, blocks)
            return get_token_limit(plan)
        except Exception as e:
            logger.exception(f"Error calculating token limit: {e}")
            return DEFAULT_TOKEN_LIMIT
