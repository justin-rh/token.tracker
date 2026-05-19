"""Pool spend computation: PoolState dataclass + compute_pool_state() factory.

Mirrors threshold_manager.py pattern exactly. Encapsulates all pool spend logic —
no UI or orchestrator code. Returns a frozen PoolState dataclass.

Key decisions implemented (from 03-CONTEXT.md):
  D-01: Only completed (non-active, non-gap) OVERAGE sessions in billing period counted
  D-02: Full session cost counted when session crosses threshold mid-run
  D-03: Pool spend recomputed from blocks on each call (pool_spend.json is a cache only)
  D-04: pool_spend.json written atomically on every compute_pool_state() call
  D-05: billing_cycle_start_day stored in config.json, not pool_spend.json
  D-06: On startup, use pool_spend.json billing_cycle_start if not stale; else recompute
  D-07/D-08: pool_size_usd (default 500.0) and billing_cycle_start_day (default 1) from config.json
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Union

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path.home() / ".claude-monitor"


@dataclass(frozen=True)
class PoolState:
    """Result of one pool spend evaluation cycle."""

    pool_size_usd: float        # from config.json (default 500.0)
    pool_spend_usd: float       # sum of OVERAGE session costs this billing period
    pool_remaining_usd: float   # pool_size_usd - pool_spend_usd (floor 0.0)
    pool_pct_spent: float       # (pool_spend_usd / pool_size_usd) * 100
    billing_cycle_start: str    # ISO date string "YYYY-MM-DD"
    is_overage: bool            # True when at least one OVERAGE session exists in period


def _read_pool_config(config_dir: Path) -> Tuple[float, int, float, Optional[datetime], bool]:
    """Read pool config from config.json.

    Returns (pool_size_usd, billing_cycle_start_day, pool_spend_seed_usd, seed_cutoff, all_sessions).

    seed_cutoff: precise UTC datetime after which log sessions are counted on top of the
        seed value. Prefers pool_spend_seed_datetime (UTC ISO string written by auto-seed);
        falls back to pool_spend_seed_date (date-only, treated as midnight UTC).
    all_sessions: if true, count every completed session toward pool spend without applying
        a per-session token threshold.

    Validation rules:
      pool_size_usd: positive int or float → default 500.0
      billing_cycle_start_day: int 1–28 → default 1
      pool_spend_seed_usd: non-negative float → default 0.0
      pool_spend_seed_datetime: UTC ISO datetime string → preferred cutoff
      pool_spend_seed_date: ISO date string "YYYY-MM-DD" → fallback cutoff (midnight UTC)
      all_sessions: bool → default False
    """
    pool_size = 500.0
    cycle_day = 1
    seed_usd = 0.0
    seed_cutoff: Optional[datetime] = None
    all_sessions = False

    config_file = config_dir / "config.json"
    if not config_file.exists():
        return pool_size, cycle_day, seed_usd, seed_cutoff, all_sessions

    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)

        raw_size = data.get("pool_size_usd")
        if isinstance(raw_size, (int, float)) and raw_size > 0:
            pool_size = float(raw_size)
        elif raw_size is not None:
            logger.warning(
                "config.json: pool_size_usd=%r is not a positive number — using default 500.0",
                raw_size,
            )

        raw_day = data.get("billing_cycle_start_day")
        if isinstance(raw_day, int) and 1 <= raw_day <= 28:
            cycle_day = raw_day
        elif raw_day is not None:
            logger.warning(
                "config.json: billing_cycle_start_day=%r is not int 1-28 — using default 1",
                raw_day,
            )

        raw_seed = data.get("pool_spend_seed_usd")
        if isinstance(raw_seed, (int, float)) and raw_seed >= 0:
            seed_usd = float(raw_seed)
        elif raw_seed is not None:
            logger.warning(
                "config.json: pool_spend_seed_usd=%r is not a non-negative number — using default 0.0",
                raw_seed,
            )

        # Prefer precise datetime; fall back to date (midnight UTC)
        raw_dt = data.get("pool_spend_seed_datetime")
        if isinstance(raw_dt, str):
            try:
                dt = datetime.fromisoformat(raw_dt)
                seed_cutoff = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning("config.json: pool_spend_seed_datetime=%r invalid — trying date", raw_dt)

        if seed_cutoff is None:
            raw_seed_date = data.get("pool_spend_seed_date")
            if isinstance(raw_seed_date, str):
                try:
                    d = date.fromisoformat(raw_seed_date)
                    seed_cutoff = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
                except ValueError:
                    logger.warning(
                        "config.json: pool_spend_seed_date=%r is not a valid ISO date — ignoring",
                        raw_seed_date,
                    )

        raw_all = data.get("all_sessions")
        if isinstance(raw_all, bool):
            all_sessions = raw_all

    except Exception as exc:
        logger.warning("Failed to read config.json for pool settings: %s", exc)

    return pool_size, cycle_day, seed_usd, seed_cutoff, all_sessions


def _derive_billing_cycle_start(cycle_day: int) -> date:
    """Derive the most recent billing cycle start date from today and cycle_day.

    If today.day >= cycle_day → this month's cycle_day.
    Otherwise → previous month's cycle_day.
    Wraps in try/except for invalid day values (belt-and-suspenders beyond config validation).
    """
    today = date.today()
    try:
        if today.day >= cycle_day:
            return today.replace(day=cycle_day)
        else:
            # Go back to previous month
            if today.month == 1:
                return today.replace(year=today.year - 1, month=12, day=cycle_day)
            else:
                return today.replace(month=today.month - 1, day=cycle_day)
    except ValueError:
        logger.warning(
            "billing_cycle_start_day=%r caused date error — using day 1", cycle_day
        )
        return today.replace(day=1)


def _in_billing_period(start_time_str: str, cutoff: Union[date, datetime]) -> bool:
    """Return True if block's startTime is at or after cutoff.

    cutoff may be a date (day-granular) or a UTC-aware datetime (precise).
    Block startTimes may be naive or timezone-aware ISO strings.
    """
    try:
        block_dt = datetime.fromisoformat(start_time_str)
        if isinstance(cutoff, datetime):
            if block_dt.tzinfo is None:
                block_dt = block_dt.replace(tzinfo=timezone.utc)
            return block_dt >= cutoff
        return block_dt.date() >= cutoff
    except (ValueError, TypeError):
        return False


def _classify_overage(block: dict, threshold_tokens: Optional[int]) -> bool:
    """Return True if block consumed more tokens than the included limit.

    During calibration (threshold_tokens is None), always returns False —
    no OVERAGE classification possible without a known threshold (Pitfall 3).
    """
    if threshold_tokens is None:
        return False  # calibrating — no threshold known, no OVERAGE
    return block.get("totalTokens", 0) > threshold_tokens


def _read_pool_spend_cache(config_dir: Path) -> dict:
    """Read pool_spend.json cache file. Returns {} on any failure.

    Mirrors LastUsedParams.load() pattern from core/settings.py.
    """
    cache_file = config_dir / "pool_spend.json"
    if not cache_file.exists():
        return {}
    try:
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to read pool_spend.json: %s", exc)
        return {}


def _write_pool_spend_cache(config_dir: Path, pool_state: "PoolState") -> None:
    """Write pool_spend.json atomically using .tmp rename pattern.

    Mirrors LastUsedParams.save() from core/settings.py exactly.
    Failure logs a warning and continues — disk full or permission error
    does not halt the monitoring loop (T-03-03 mitigation).
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pool_spend_usd": pool_state.pool_spend_usd,
        "billing_cycle_start": pool_state.billing_cycle_start,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    final_path = config_dir / "pool_spend.json"
    temp_file = final_path.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(final_path)
    except Exception as exc:
        logger.warning("Failed to write pool_spend.json: %s", exc)


def compute_pool_state(
    blocks: list,
    threshold_state,  # ThresholdState | None
    config_dir: Optional[Path] = None,
) -> "PoolState":
    """Compute pool spend state from serialized block dicts and threshold state.

    This is the public factory function. Mirrors get_threshold() from threshold_manager.py.

    Args:
        blocks: Serialized block dicts with camelCase keys (isActive, isGap, totalTokens,
                costUSD, startTime). From data/analysis.py:_create_base_block_dict().
        threshold_state: ThresholdState (or None). When calibrating,
                         threshold_tokens is None and pool_spend_usd will be 0.0.
        config_dir: Override for ~/.claude-monitor dir (used in tests). Defaults to
                    Path.home() / ".claude-monitor".

    Returns:
        PoolState frozen dataclass with pool spend metrics for the current billing period.
    """
    if config_dir is None:
        config_dir = _DEFAULT_CONFIG_DIR

    # Read pool configuration from config.json (D-07/D-08)
    pool_size_usd, cycle_day, seed_usd, seed_cutoff, all_sessions = _read_pool_config(config_dir)

    # Determine billing cycle start — check cache first (D-06, Pitfall 4)
    current_cycle_start = _derive_billing_cycle_start(cycle_day)
    cycle_start: date

    cached = _read_pool_spend_cache(config_dir)
    if cached.get("billing_cycle_start"):
        try:
            cached_start = date.fromisoformat(cached["billing_cycle_start"])
            # Stale check (Pitfall 4): if cached start < current cycle start, ignore cache
            if cached_start >= current_cycle_start:
                cycle_start = cached_start
            else:
                cycle_start = current_cycle_start
        except (ValueError, TypeError):
            cycle_start = current_cycle_start
    else:
        cycle_start = current_cycle_start

    billing_cycle_start_str = cycle_start.isoformat()

    # D-24 (04-CONTEXT.md): Log billing cycle reset event when cycle_start changes.
    # Detects transition: cached billing_cycle_start != current cycle_start → reset occurred.
    cached_cycle_str = cached.get("billing_cycle_start")
    if cached_cycle_str and cached_cycle_str != billing_cycle_start_str:
        logger.info(
            "Billing cycle reset — pool spend cleared to $0.00"
        )

    # Get threshold_tokens — None when calibrating (Pitfall 3)
    threshold_tokens: Optional[int] = None
    if threshold_state is not None:
        threshold_tokens = threshold_state.threshold_tokens

    # When a seed is set, only count log sessions after seed_cutoff — sessions before
    # are already captured by pool_spend_seed_usd from the Anthropic billing dashboard.
    log_cutoff: Union[date, datetime] = cycle_start
    if seed_cutoff is not None and seed_cutoff.date() > cycle_start:
        log_cutoff = seed_cutoff

    # Sum OVERAGE session costs since log_cutoff (D-01, D-02, D-03)
    pool_spend_usd = seed_usd
    for block in blocks:
        # Skip gap blocks (idle placeholders). Active blocks are included so the
        # pool bar reflects real-time spend during an ongoing session.
        if block.get("isGap", False):
            continue
        # Skip sessions before the log cutoff (billing period start or seed date)
        if not _in_billing_period(block.get("startTime", ""), log_cutoff):
            continue
        # OVERAGE classification: all sessions (Teams/Enterprise) or threshold-based (Max plan)
        if all_sessions or _classify_overage(block, threshold_tokens):
            pool_spend_usd += block.get("costUSD", 0.0)

    # Derived metrics
    pool_remaining_usd = max(0.0, pool_size_usd - pool_spend_usd)
    pool_pct_spent = (pool_spend_usd / pool_size_usd * 100) if pool_size_usd > 0 else 0.0

    # is_overage: True when threshold is known AND at least one OVERAGE session exists
    is_overage = pool_spend_usd > 0.0 and threshold_tokens is not None

    result = PoolState(
        pool_size_usd=pool_size_usd,
        pool_spend_usd=pool_spend_usd,
        pool_remaining_usd=pool_remaining_usd,
        pool_pct_spent=pool_pct_spent,
        billing_cycle_start=billing_cycle_start_str,
        is_overage=is_overage,
    )

    # Write cache atomically on every cycle (D-04, OVGE-05)
    _write_pool_spend_cache(config_dir, result)

    return result
