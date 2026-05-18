"""Simplified data reader for Claude Monitor.

Combines functionality from file_reader, filter, mapper, and processor
into a single cohesive module.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from datetime import timezone as tz
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from claude_monitor.core.data_processors import (
    DataConverter,
    TimestampProcessor,
    TokenExtractor,
)
from claude_monitor.core.models import CostMode, UsageEntry
from claude_monitor.core.pricing import PricingCalculator
from claude_monitor.error_handling import report_file_error
from claude_monitor.utils.time_utils import TimezoneHandler

FIELD_COST_USD = "cost_usd"
FIELD_MODEL = "model"
TOKEN_INPUT = "input_tokens"
TOKEN_OUTPUT = "output_tokens"

logger = logging.getLogger(__name__)

# Module-level list of JSONL files that were locked (PermissionError) during the
# most recent read call.  Reset at the start of each load_usage_entries() call.
# The UI layer reads this after each call to show an "(active session — data not
# yet visible)" indicator per D-05.
LOCKED_FILES: List[Path] = []


def _deduplicate_entries(entries: list) -> list:
    """
    Collapse streaming placeholder entries by requestId.
    Claude Code writes 2-10 JSONL entries per API request during streaming.
    All share the same requestId. The final entry has the true output_tokens count.
    Selecting max(output_tokens) per requestId gives the correct final entry.

    Entries without a requestId field are passed through unchanged (tool-use results,
    system messages, etc. — these are not streaming API entries).

    This is the fix for the 100-174x token inflation bug (PITFALLS.md, GitHub #22686).
    Strategy: max(output_tokens) per requestId (final streaming chunk).
    """
    keyed: dict = {}  # requestId -> best entry so far

    no_request_id = []
    for entry in entries:
        rid = entry.get("requestId") or entry.get("request_id")
        if rid is None:
            no_request_id.append(entry)
            continue

        existing = keyed.get(rid)
        if existing is None:
            keyed[rid] = entry
        else:
            # Keep the entry with higher output_tokens (final streaming chunk)
            existing_out = (
                existing.get("message", {}).get("usage", {}).get("output_tokens", 0)
            )
            new_out = entry.get("message", {}).get("usage", {}).get("output_tokens", 0)
            if new_out > existing_out:
                keyed[rid] = entry

    return list(keyed.values()) + no_request_id


def _get_default_claude_projects_path() -> Path:
    """Return the Claude Code projects directory for Windows.

    Uses %APPDATA% explicitly per D-03 — this is AppData\\Roaming\\.claude\\projects,
    NOT ~\\.claude\\projects (which would be the USERPROFILE root, not AppData).
    """
    return Path(os.environ["APPDATA"]) / ".claude" / "projects"


def load_usage_entries(
    data_path: Optional[str] = None,
    hours_back: Optional[int] = None,
    mode: CostMode = CostMode.AUTO,
    include_raw: bool = False,
) -> Tuple[List[UsageEntry], Optional[List[Dict[str, Any]]]]:
    """Load and convert JSONL files to UsageEntry objects.

    Args:
        data_path: Path to Claude data directory (defaults to ~/.claude/projects)
        hours_back: Only include entries from last N hours
        mode: Cost calculation mode
        include_raw: Whether to return raw JSON data alongside entries

    Returns:
        Tuple of (usage_entries, raw_data) where raw_data is None unless include_raw=True
    """
    global LOCKED_FILES
    LOCKED_FILES = []

    if data_path is None or data_path == "":
        data_path = _get_default_claude_projects_path()
    else:
        data_path = Path(data_path)

    if not data_path.exists():
        print(
            f"[WARNING] Claude projects directory not found: {data_path}",
            file=sys.stderr,
        )
        print(
            "[WARNING] Check that Claude Code has been run at least once.",
            file=sys.stderr,
        )

    timezone_handler = TimezoneHandler()
    pricing_calculator = PricingCalculator()

    cutoff_time = None
    if hours_back:
        cutoff_time = datetime.now(tz.utc) - timedelta(hours=hours_back)

    jsonl_files = _find_jsonl_files(data_path)
    if not jsonl_files:
        logger.warning("No JSONL files found in %s", data_path)
        return [], None

    all_entries: List[UsageEntry] = []
    raw_entries: Optional[List[Dict[str, Any]]] = [] if include_raw else None
    processed_hashes: Set[str] = set()

    for file_path in jsonl_files:
        entries, raw_data = _process_single_file(
            file_path,
            mode,
            cutoff_time,
            processed_hashes,
            include_raw,
            timezone_handler,
            pricing_calculator,
        )
        all_entries.extend(entries)
        if include_raw and raw_data:
            raw_entries.extend(raw_data)

    all_entries.sort(key=lambda e: e.timestamp)

    logger.info(f"Processed {len(all_entries)} entries from {len(jsonl_files)} files")

    return all_entries, raw_entries


def load_all_raw_entries(data_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load all raw JSONL entries without processing.

    Args:
        data_path: Path to Claude data directory

    Returns:
        List of raw JSON dictionaries
    """
    if data_path is None or data_path == "":
        data_path = _get_default_claude_projects_path()
    else:
        data_path = Path(data_path)
    jsonl_files = _find_jsonl_files(data_path)

    all_raw_entries: List[Dict[str, Any]] = []
    for file_path in jsonl_files:
        try:
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        all_raw_entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except PermissionError:
            # WinError 32: Claude Code holds a write lock on the active session file.
            # Skip this file for this refresh cycle.
            logger.warning("Permission denied reading %s — skipping (file locked)", file_path)
        except Exception as e:
            logger.exception(f"Error loading raw entries from {file_path}: {e}")

    return all_raw_entries


def _find_jsonl_files(data_path: Path) -> List[Path]:
    """Find all .jsonl files in the data directory."""
    if not data_path.exists():
        logger.warning("Data path does not exist: %s", data_path)
        return []
    return list(data_path.rglob("*.jsonl"))


def _process_single_file(
    file_path: Path,
    mode: CostMode,
    cutoff_time: Optional[datetime],
    processed_hashes: Set[str],
    include_raw: bool,
    timezone_handler: TimezoneHandler,
    pricing_calculator: PricingCalculator,
) -> Tuple[List[UsageEntry], Optional[List[Dict[str, Any]]]]:
    """Process a single JSONL file."""
    entries: List[UsageEntry] = []
    raw_data: Optional[List[Dict[str, Any]]] = [] if include_raw else None

    try:
        entries_read = 0
        entries_filtered = 0
        entries_mapped = 0

        # Collect all raw JSON entries from this file first, before any processing.
        # Deduplication by requestId (max output_tokens strategy) must happen on the
        # complete set of entries for a file — not line-by-line — so we read all lines
        # into raw_parsed, then deduplicate, then map to UsageEntry objects.
        raw_parsed: List[Dict[str, Any]] = []
        with open(file_path, encoding="utf-8-sig", newline="") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries_read += 1
                    raw_parsed.append(data)
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse JSON line in {file_path}: {e}")
                    continue

        # Deduplicate by requestId (max output_tokens = final streaming chunk).
        # This collapses the 2-10 streaming placeholder entries per API request into
        # one correct entry, preventing 100-174x token count inflation (PITFALLS.md).
        deduped_parsed = _deduplicate_entries(raw_parsed)
        logger.debug(
            f"File {file_path.name}: {entries_read} read, "
            f"{len(deduped_parsed)} after requestId dedup "
            f"({entries_read - len(deduped_parsed)} duplicates removed)"
        )

        for data in deduped_parsed:
            if not _should_process_entry(
                data, cutoff_time, processed_hashes, timezone_handler
            ):
                entries_filtered += 1
                continue

            entry = _map_to_usage_entry(
                data, mode, timezone_handler, pricing_calculator
            )
            if entry:
                entries_mapped += 1
                entries.append(entry)
                _update_processed_hashes(data, processed_hashes)

            if include_raw:
                raw_data.append(data)

        logger.debug(
            f"File {file_path.name}: {entries_read} read, "
            f"{entries_filtered} filtered out, {entries_mapped} successfully mapped"
        )

    except PermissionError:
        # WinError 32: Claude Code holds a write lock on the active session file.
        # Skip this file for this refresh cycle and record it so the UI can show
        # the "(active session — data not yet visible)" indicator per D-05.
        LOCKED_FILES.append(file_path)
        logger.warning(
            "Permission denied reading %s — file locked by another process (active session)",
            file_path,
        )
        return [], None

    except Exception as e:
        logger.warning("Failed to read file %s: %s", file_path, e)
        report_file_error(
            exception=e,
            file_path=str(file_path),
            operation="read",
            additional_context={"file_exists": file_path.exists()},
        )
        return [], None

    return entries, raw_data


def _should_process_entry(
    data: Dict[str, Any],
    cutoff_time: Optional[datetime],
    processed_hashes: Set[str],
    timezone_handler: TimezoneHandler,
) -> bool:
    """Check if entry should be processed based on time and uniqueness."""
    if cutoff_time:
        timestamp_str = data.get("timestamp")
        if timestamp_str:
            processor = TimestampProcessor(timezone_handler)
            timestamp = processor.parse_timestamp(timestamp_str)
            if timestamp and timestamp < cutoff_time:
                return False

    unique_hash = _create_unique_hash(data)
    return not (unique_hash and unique_hash in processed_hashes)


def _create_unique_hash(data: Dict[str, Any]) -> Optional[str]:
    """Create unique hash for deduplication."""
    message_id = data.get("message_id") or (
        data.get("message", {}).get("id")
        if isinstance(data.get("message"), dict)
        else None
    )
    request_id = data.get("requestId") or data.get("request_id")

    return f"{message_id}:{request_id}" if message_id and request_id else None


def _update_processed_hashes(data: Dict[str, Any], processed_hashes: Set[str]) -> None:
    """Update the processed hashes set with current entry's hash."""
    unique_hash = _create_unique_hash(data)
    if unique_hash:
        processed_hashes.add(unique_hash)


def _map_to_usage_entry(
    data: Dict[str, Any],
    mode: CostMode,
    timezone_handler: TimezoneHandler,
    pricing_calculator: PricingCalculator,
) -> Optional[UsageEntry]:
    """Map raw data to UsageEntry with proper cost calculation."""
    try:
        timestamp_processor = TimestampProcessor(timezone_handler)
        timestamp = timestamp_processor.parse_timestamp(data.get("timestamp", ""))
        if not timestamp:
            return None

        token_data = TokenExtractor.extract_tokens(data)
        if not any(v for k, v in token_data.items() if k != "total_tokens"):
            return None

        model = DataConverter.extract_model_name(data, default="unknown")

        entry_data: Dict[str, Any] = {
            FIELD_MODEL: model,
            TOKEN_INPUT: token_data["input_tokens"],
            TOKEN_OUTPUT: token_data["output_tokens"],
            "cache_creation_tokens": token_data.get("cache_creation_tokens", 0),
            "cache_read_tokens": token_data.get("cache_read_tokens", 0),
            FIELD_COST_USD: data.get("cost") or data.get(FIELD_COST_USD),
        }
        cost_usd = pricing_calculator.calculate_cost_for_entry(entry_data, mode)

        message = data.get("message", {})
        message_id = data.get("message_id") or message.get("id") or ""
        request_id = data.get("request_id") or data.get("requestId") or "unknown"
        session_id = data.get("sessionId") or data.get("session_id") or ""

        return UsageEntry(
            timestamp=timestamp,
            input_tokens=token_data["input_tokens"],
            output_tokens=token_data["output_tokens"],
            cache_creation_tokens=token_data.get("cache_creation_tokens", 0),
            cache_read_tokens=token_data.get("cache_read_tokens", 0),
            cost_usd=cost_usd,
            model=model,
            message_id=message_id,
            request_id=request_id,
            session_id=session_id,
        )

    except (KeyError, ValueError, TypeError, AttributeError) as e:
        logger.debug(f"Failed to map entry: {type(e).__name__}: {e}")
        return None


class UsageEntryMapper:
    """Compatibility wrapper for legacy UsageEntryMapper interface.

    This class provides backward compatibility for tests that expect
    the old UsageEntryMapper interface, wrapping the new functional
    approach in _map_to_usage_entry.
    """

    def __init__(
        self, pricing_calculator: PricingCalculator, timezone_handler: TimezoneHandler
    ):
        """Initialize with required components."""
        self.pricing_calculator = pricing_calculator
        self.timezone_handler = timezone_handler

    def map(self, data: Dict[str, Any], mode: CostMode) -> Optional[UsageEntry]:
        """Map raw data to UsageEntry - compatibility interface."""
        return _map_to_usage_entry(
            data, mode, self.timezone_handler, self.pricing_calculator
        )

    def _has_valid_tokens(self, tokens: Dict[str, int]) -> bool:
        """Check if tokens are valid (for test compatibility)."""
        return any(v > 0 for v in tokens.values())

    def _extract_timestamp(self, data: Dict[str, Any]) -> Optional[datetime]:
        """Extract timestamp (for test compatibility)."""
        if "timestamp" not in data:
            return None
        processor = TimestampProcessor(self.timezone_handler)
        return processor.parse_timestamp(data["timestamp"])

    def _extract_model(self, data: Dict[str, Any]) -> str:
        """Extract model name (for test compatibility)."""
        return DataConverter.extract_model_name(data, default="unknown")

    def _extract_metadata(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Extract metadata (for test compatibility)."""
        message = data.get("message", {})
        return {
            "message_id": data.get("message_id") or message.get("id", ""),
            "request_id": data.get("request_id") or data.get("requestId", "unknown"),
        }
