"""Background WebPoller thread for claude.ai usage data.

Polls fetch_web_usage() immediately on start, then every 300 seconds using
threading.Event.wait() for the interval (not time.sleep). A threading.Lock
protects the cached WebUsageData for thread-safe reads from the main thread.

Threading model (per STATE.md):
  - Main thread: Rich Live display (1s sleep loop)
  - MonitoringThread: JSONL read + callbacks (10s)
  - WebPollerThread: claude.ai HTTP fetch (300s Event.wait) — THIS FILE

Usage:
    web_poller = WebPoller(org_id="...", config_dir=Path.home() / ".claude-monitor")
    web_poller.start()  # starts daemon thread, polls immediately
    ...
    data = web_poller.get_web_usage()       # thread-safe read
    last = web_poller.get_last_sync_time()  # thread-safe read
    ...
    web_poller.stop()   # signals stop event; daemon exits on next wake
"""
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from claude_monitor.core.models import WebUsageData
from claude_monitor.core.usage_fetcher import fetch_web_usage

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".claude-monitor"


class WebPoller(threading.Thread):
    """Daemon thread that fetches claude.ai usage data every 300 seconds.

    Inherits threading.Thread with daemon=True — thread terminates automatically
    when the main process exits (no explicit join needed).

    Thread safety:
      - _web_usage and _last_sync_time are only written inside _poll_once()
        under _cache_lock. All public reads acquire the same lock.
      - _stop_event is a threading.Event — set() and wait() are thread-safe.

    Per D-12 (04-CONTEXT.md):
      - Uses threading.Event for 300s sleep (not time.sleep)
      - threading.Lock protects cached WebUsageData
      - daemon=True
    Per D-13:
      - On success: updates cache + records last_sync_time
      - On failure: logs warning, leaves previous cache intact
    """

    def __init__(self, org_id: str, config_dir: Optional[Path] = None) -> None:
        """Initialize WebPoller.

        Args:
            org_id: Anthropic organization UUID. Required — must be resolved
                    before constructing WebPoller (Pitfall 6 in RESEARCH.md).
            config_dir: Path to ~/.claude-monitor config dir. Defaults to
                        Path.home() / ".claude-monitor".
        """
        super().__init__(name="WebPollerThread", daemon=True)
        self._org_id = org_id
        self._config_dir = config_dir or _CONFIG_DIR
        self._stop_event: threading.Event = threading.Event()
        self._cache_lock: threading.Lock = threading.Lock()
        self._web_usage: Optional[WebUsageData] = None
        self._last_sync_time: Optional[datetime] = None

    def run(self) -> None:
        """Poll immediately on start, then every 300s until stopped.

        Loop idiom: while not self._stop_event.wait(300)
          - wait(300) returns False on timeout → continue polling
          - wait(300) returns True when stop() is called → not True = False → exit loop
        """
        logger.info("WebPoller: starting (300s interval, org_id omitted)")
        self._poll_once()
        while not self._stop_event.wait(300):
            self._poll_once()
        logger.info("WebPoller: stopped")

    def stop(self) -> None:
        """Signal the poller to stop. Returns immediately.

        No join() needed — daemon thread dies with the process.
        Thread wakes from Event.wait() within milliseconds of set().
        """
        logger.debug("WebPoller: stop signal sent")
        self._stop_event.set()

    def get_web_usage(self) -> Optional[WebUsageData]:
        """Thread-safe read of the latest cached WebUsageData.

        Returns None if no successful fetch has occurred yet.
        Acquires _cache_lock briefly; does not block polling.
        """
        with self._cache_lock:
            return self._web_usage

    def get_last_sync_time(self) -> Optional[datetime]:
        """Thread-safe read of the last successful sync timestamp (UTC).

        Returns None if no successful fetch has occurred yet.
        """
        with self._cache_lock:
            return self._last_sync_time

    def _poll_once(self) -> None:
        """Execute one fetch cycle and update cache on success.

        On success: acquires lock, updates _web_usage and _last_sync_time.
        On failure: logs warning, leaves previous cache values intact (D-13).
        """
        result = fetch_web_usage(self._org_id, self._config_dir)
        if result is not None:
            with self._cache_lock:
                self._web_usage = result
                self._last_sync_time = datetime.now(timezone.utc)
            logger.debug(
                "WebPoller: cache updated, utilization=%.1f%%", result.utilization_pct
            )
        else:
            logger.warning("WebPoller: fetch failed — retaining previous cache")
