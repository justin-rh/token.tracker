"""Per-project token breakdown: ProjectBreakdown factory function.

Scans JSONL files by project directory, deduplicates entries by requestId,
aggregates tokens per project for today (UTC) and the current billing month,
and returns a frozen ProjectBreakdown dataclass.

Key decisions implemented (from 06-02-PLAN.md):
  D-01: Display name = last hyphen-separated segment of project slug
        e.g. "C:-Users-justin-rhoda-token-tracker".split("-")[-1] == "tracker"
  D-02: _deduplicate_entries imported from data/reader.py — logic NOT duplicated
  D-03: encoding="utf-8-sig" used for JSONL reads (strips Windows BOM)
  D-04: PermissionError caught per-file (WinError 32 — file locked by active session)
  D-05: billing_cycle_start_day read from config.json (default 1, validated 1-28)
  D-06: Zero-token entries excluded from both today and billing_month lists
"""

import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from claude_monitor.core.models import ProjectBreakdown
from claude_monitor.data.reader import _deduplicate_entries, _find_jsonl_files

logger = logging.getLogger(__name__)

_DEFAULT_DATA_PATH = Path(os.environ["APPDATA"]) / ".claude" / "projects"
_DEFAULT_CONFIG_DIR = Path.home() / ".claude-monitor"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _read_cycle_day(config_dir: Path) -> int:
    """Read billing_cycle_start_day from config_dir/config.json.

    Returns an int in range 1-28. Falls back to 1 on any error or invalid value.
    Mirrors the validation block in core/pool_state_manager.py._read_pool_config().
    """
    cycle_day = 1
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return cycle_day

    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)

        raw_day = data.get("billing_cycle_start_day")
        if isinstance(raw_day, int) and 1 <= raw_day <= 28:
            cycle_day = raw_day
        elif raw_day is not None:
            logger.warning(
                "config.json: billing_cycle_start_day=%r is not int 1-28 — using default 1",
                raw_day,
            )

    except Exception as exc:
        logger.warning("Failed to read config.json for billing cycle day: %s", exc)

    return cycle_day


def _derive_billing_cycle_start(cycle_day: int) -> date:
    """Derive the most recent billing cycle start date from today and cycle_day.

    If today.day >= cycle_day → this month's cycle_day.
    Otherwise → previous month's cycle_day.
    Wraps in try/except for invalid day values.

    Exact replica of core/pool_state_manager.py._derive_billing_cycle_start().
    """
    today = date.today()
    try:
        if today.day >= cycle_day:
            return today.replace(day=cycle_day)
        else:
            if today.month == 1:
                return today.replace(year=today.year - 1, month=12, day=cycle_day)
            else:
                return today.replace(month=today.month - 1, day=cycle_day)
    except ValueError:
        logger.warning("billing_cycle_start_day=%r caused date error — using day 1", cycle_day)
        return today.replace(day=1)


# ---------------------------------------------------------------------------
# Public factory function
# ---------------------------------------------------------------------------

def compute_project_breakdown(
    data_path: Optional[Path] = None,
    config_dir: Optional[Path] = None,
) -> ProjectBreakdown:
    """Scan JSONL files by project directory and return a ProjectBreakdown.

    Algorithm:
      1. Apply defaults for data_path and config_dir.
      2. Read billing cycle start day from config; derive billing_start date.
      3. Compute today_date as the current UTC calendar day.
      4. For each JSONL file found under data_path (rglob):
         a. Extract slug = file_path.parent.name; display_name = slug.split("-")[-1].
         b. Parse all lines using utf-8-sig encoding (strips Windows BOM).
         c. Skip PermissionError files (locked by active session — WinError 32).
         d. Skip any other Exception per file (non-fatal; log warning).
         e. Deduplicate entries by requestId via _deduplicate_entries (imported).
         f. For each deduplicated entry:
            - Parse timestamp; skip if missing/invalid.
            - Compute total tokens (input + output + cache_creation + cache_read).
            - Skip if total == 0 (zero-token entries excluded, D-06).
            - Accumulate into today_tokens if ts.date() == today_date.
            - Accumulate into month_tokens if ts.date() >= billing_start.
      5. Sort each dict descending by value; take top 5.
      6. Return ProjectBreakdown(today, billing_month, as_of=datetime.now(UTC)).

    Args:
        data_path: Root of the project JSONL directories. Defaults to
                   %APPDATA%\\.claude\\projects.
        config_dir: Directory containing config.json. Defaults to
                    ~/.claude-monitor.

    Returns:
        ProjectBreakdown with today and billing_month ranked lists.
    """
    if data_path is None:
        data_path = _DEFAULT_DATA_PATH
    if config_dir is None:
        config_dir = _DEFAULT_CONFIG_DIR

    cycle_day = _read_cycle_day(config_dir)
    billing_start: date = _derive_billing_cycle_start(cycle_day)
    today_date: date = datetime.now(timezone.utc).date()

    today_tokens: dict[str, int] = defaultdict(int)
    month_tokens: dict[str, int] = defaultdict(int)

    for file_path in _find_jsonl_files(data_path):
        slug = file_path.parent.name
        display_name = slug.split("-")[-1]

        raw_parsed: list = []
        try:
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        raw_parsed.append(data)
                    except json.JSONDecodeError:
                        continue
        except PermissionError:
            logger.warning(
                "Permission denied reading %s — file locked by another process (active session)",
                file_path,
            )
            continue
        except Exception as exc:
            logger.warning("Unexpected error reading %s — skipping file: %s", file_path, exc)
            continue

        entries = _deduplicate_entries(raw_parsed)

        for entry in entries:
            ts_str = entry.get("timestamp", "")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
            except (ValueError, TypeError):
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            usage = entry.get("message", {}).get("usage", {})
            total = (
                usage.get("input_tokens", 0)
                + usage.get("output_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0)
            )

            if total == 0:
                continue

            entry_date = ts.date()
            if entry_date == today_date:
                today_tokens[display_name] += total
            if entry_date >= billing_start:
                month_tokens[display_name] += total

    today_top5 = sorted(today_tokens.items(), key=lambda x: x[1], reverse=True)[:5]
    month_top5 = sorted(month_tokens.items(), key=lambda x: x[1], reverse=True)[:5]

    return ProjectBreakdown(
        today=today_top5,
        billing_month=month_top5,
        as_of=datetime.now(timezone.utc),
    )
