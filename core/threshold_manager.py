"""Threshold state detection: manual override, cold-start calibration, P90 auto."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

COLD_START_MINIMUM = 10  # D-02: hardcoded, not configurable

_DEFAULT_CONFIG_DIR = Path.home() / ".claude-monitor"


@dataclass(frozen=True)
class ThresholdState:
    """Result of one threshold evaluation cycle."""

    status: Literal["calibrating", "auto", "manual"]
    threshold_tokens: Optional[int]    # None when calibrating
    completed_session_count: int       # always populated (for display N/10)
    cold_start_minimum: int = 10       # informational — matches COLD_START_MINIMUM


def _read_manual_override(config_dir: Path) -> Optional[int]:
    """Read overage_threshold_tokens from config.json, or None if absent/invalid.

    Mirrors LastUsedParams.load() pattern from core/settings.py.
    D-03: config.json lives in ~/.claude-monitor/config.json
    D-04: if present and valid positive int, caller skips P90 entirely.
    """
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return None
    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        value = data.get("overage_threshold_tokens")
        if isinstance(value, int) and value > 0:
            return value
        if value is not None:
            logger.warning(
                "config.json: overage_threshold_tokens=%r is not a positive int "
                "— falling back to P90",
                value,
            )
    except Exception as exc:
        logger.warning("Failed to read config.json: %s", exc)
    return None


def _count_completed_sessions(blocks: list) -> int:
    """Count non-active, non-gap blocks with totalTokens > 0.

    D-01: All completed (non-active, non-gap) blocks feed both P90 and cold-start.
    Uses camelCase keys (isGap, isActive, totalTokens) — the serialized dict format
    from data/analysis.py:_create_base_block_dict(). NOT the SessionBlock object attrs.
    """
    return sum(
        1
        for b in blocks
        if not b.get("isGap", False)
        and not b.get("isActive", False)
        and b.get("totalTokens", 0) > 0
    )


def get_threshold(blocks: list, config_dir: Optional[Path] = None) -> ThresholdState:
    """Evaluate threshold state from block history and config.json.

    Decision order (per CONTEXT.md D-04 takes priority):
      1. If config.json has valid overage_threshold_tokens → MANUAL (skip P90)
      2. Elif completed_count < 10 → CALIBRATING (no threshold yet)
      3. Else → AUTO (run P90 on completed blocks)

    Args:
        blocks: Serialized block dicts with camelCase keys (isActive, isGap, totalTokens).
                Do NOT pass SessionBlock objects — raises TypeError.
        config_dir: Override for ~/.claude-monitor dir (used in tests). Defaults to
                    Path.home() / ".claude-monitor".

    Returns:
        ThresholdState with status in {"calibrating", "auto", "manual"}

    Raises:
        TypeError: If blocks contains SessionBlock objects instead of dicts.
    """
    if config_dir is None:
        config_dir = _DEFAULT_CONFIG_DIR

    # Guard against passing SessionBlock objects (wrong type — use serialized dicts)
    if blocks and hasattr(blocks[0], "is_gap"):
        raise TypeError(
            "get_threshold() expects serialized dict blocks (isGap key), "
            "not SessionBlock objects (is_gap attr). Pass data['blocks'] from monitoring_data."
        )

    # D-04: manual override check first — if present, skip P90 entirely
    manual = _read_manual_override(config_dir)
    if manual is not None:
        return ThresholdState(
            status="manual",
            threshold_tokens=manual,
            completed_session_count=_count_completed_sessions(blocks),
        )

    # D-01 + D-02: count completed blocks for cold-start guard
    count = _count_completed_sessions(blocks)
    if count < COLD_START_MINIMUM:
        return ThresholdState(
            status="calibrating",
            threshold_tokens=None,
            completed_session_count=count,
        )

    # D-01: all completed blocks feed P90
    completed = [
        b
        for b in blocks
        if not b.get("isGap", False)
        and not b.get("isActive", False)
        and b.get("totalTokens", 0) > 0
    ]

    from claude_monitor.core.p90_calculator import P90Calculator

    p90 = P90Calculator().calculate_p90_limit(completed)

    if p90 is None:
        # Belt-and-suspenders: cold-start guard fires first, so this should not
        # happen. Fall back to calibrating rather than returning garbage.
        logger.warning(
            "P90Calculator returned None despite %d completed sessions", count
        )
        return ThresholdState(
            status="calibrating", threshold_tokens=None, completed_session_count=count
        )

    return ThresholdState(status="auto", threshold_tokens=p90, completed_session_count=count)
