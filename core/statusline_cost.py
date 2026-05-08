"""
statusline_cost.py — Read cost.total_cost_usd from ~/.claude/statusline.jsonl.

statusline.jsonl is written by Claude Code and contains one JSON record per line,
each representing a session's most recent status snapshot. The cost.total_cost_usd
field is the most accurate local cost estimate available (more accurate than
computing cost from raw JSONL token counts).

Per D-06: This is the PRIMARY cost source.
Per D-07: One entry per session; match by session ID or timestamp.
Per D-08: The costUSD field in session JSONL is NOT used (removed in v1.0.9).
"""
import json
from pathlib import Path
from typing import Optional


def _get_statusline_path() -> Path:
    """
    statusline.jsonl lives in the user's .claude directory (home dir, NOT AppData).
    This is different from the projects/ directory which uses APPDATA.
    """
    return Path.home() / ".claude" / "statusline.jsonl"


def read_statusline_costs() -> dict:
    """
    Read all entries from statusline.jsonl and return a dict mapping
    session identifier to cost_usd float.

    Returns:
        dict: Keys are session identifiers (session_id string, or ISO timestamp string
              if no session_id field), values are float cost_usd.
        Returns {} if the file does not exist or cannot be read.

    The statusline.jsonl schema (from official Claude Code docs):
        {
          "session_id": "...",          # unique session identifier
          "cost": {
            "total_cost_usd": 0.1234    # cumulative cost for this session
          },
          "timestamp": "2026-...",      # ISO 8601 UTC
          ...other fields...
        }

    Per D-07: if the actual on-disk structure differs from the above, the caller
    (data/analyzer.py) adapts by falling back to pricing engine.
    """
    path = _get_statusline_path()
    if not path.exists():
        return {}

    costs: dict = {}
    try:
        with open(path, 'r', encoding='utf-8-sig', newline='') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                cost_usd = _extract_cost(record)
                if cost_usd is None:
                    continue

                key = _extract_key(record)
                if key:
                    # If multiple entries share the same key, keep the most recent
                    # (last-write wins — statusline is continuously updated)
                    costs[key] = cost_usd

    except PermissionError:
        # statusline.jsonl is unlikely to be locked (not a session file),
        # but handle defensively
        return {}

    return costs


def _extract_cost(record: dict) -> Optional[float]:
    """Extract cost.total_cost_usd from a statusline record."""
    cost_block = record.get("cost")
    if cost_block is None:
        return None
    raw = cost_block.get("total_cost_usd")
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _extract_key(record: dict) -> Optional[str]:
    """
    Return a stable key for matching statusline entries to session blocks.
    Prefer session_id; fall back to timestamp string.
    """
    session_id = record.get("session_id") or record.get("sessionId")
    if session_id:
        return str(session_id)

    timestamp = record.get("timestamp")
    if timestamp:
        return str(timestamp)

    return None
