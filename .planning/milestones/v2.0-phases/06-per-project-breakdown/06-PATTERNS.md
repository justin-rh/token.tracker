# Phase 6: Per-Project Breakdown - Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 5
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/models.py` | model | transform | `core/models.py` (WebUsageData) | exact |
| `core/project_breakdown.py` | service | batch / file-I/O | `core/pool_state_manager.py` | exact |
| `monitoring/orchestrator.py` | orchestrator | request-response | `monitoring/orchestrator.py` (pool_state / web_usage additions) | exact |
| `ui/session_display.py` | component | request-response | `ui/session_display.py` (pool_state / web_usage rendering blocks) | exact |
| `data/reader.py` | utility | file-I/O | `data/reader.py` | read-only reference |

---

## Pattern Assignments

### `core/models.py` — add `ProjectBreakdown` frozen dataclass

**Analog:** `core/models.py`, lines 114-131 (`WebUsageData`)

**Frozen dataclass pattern** (lines 114-131):
```python
@dataclass(frozen=True)
class WebUsageData:
    """Authoritative usage data fetched from claude.ai API.
    ...
    """
    utilization_pct: float
    reset_at: datetime
    fetched_at: datetime
    plan_limit_tokens: Optional[int]
```

**New dataclass to add** (mirror this pattern exactly):
```python
@dataclass(frozen=True)
class ProjectBreakdown:
    """Per-project token breakdown computed from local JSONL files."""
    today: list[tuple[str, int]]         # [(display_name, total_tokens), ...] top 5, UTC today
    billing_month: list[tuple[str, int]] # [(display_name, total_tokens), ...] top 5, billing month
    as_of: datetime                       # UTC timestamp when computed
```

**Import additions needed** (lines 1-8, existing imports already cover `dataclass`, `datetime`, `Optional`):
```python
from dataclasses import dataclass, field   # already present
from datetime import datetime              # already present
from typing import Any, Dict, List, Optional  # already present
```
No new imports needed — `list[tuple[str, int]]` uses built-in generics (Python 3.11+, matches `requires-python = ">=3.11"` in pyproject.toml).

---

### `core/project_breakdown.py` — new module

**Analog:** `core/pool_state_manager.py`

**Module docstring pattern** (lines 1-14 of pool_state_manager.py):
```python
"""Pool spend computation: PoolState dataclass + compute_pool_state() factory.

Mirrors threshold_manager.py pattern exactly. Encapsulates all pool spend logic —
no UI or orchestrator code. Returns a frozen PoolState dataclass.
...
"""
```
New module docstring should follow the same single-responsibility description style.

**Imports pattern** (lines 1-23 of pool_state_manager.py):
```python
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Union

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path.home() / ".claude-monitor"
```
For `project_breakdown.py`, replace `json` with nothing (no JSON cache needed), keep `logging`, `datetime`, `timezone`, `Path`. Add `os` for APPDATA path. The data path default mirrors `data/reader.py:_get_default_claude_projects_path()`:
```python
import os
_DEFAULT_DATA_PATH = Path(os.environ["APPDATA"]) / ".claude" / "projects"
_DEFAULT_CONFIG_DIR = Path.home() / ".claude-monitor"
```

**Config read pattern** (pool_state_manager.py lines 40-128, `_read_pool_config`):
```python
def _read_pool_config(config_dir: Path) -> Tuple[float, int, ...]:
    cycle_day = 1
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return ..., cycle_day, ...
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
        logger.warning("Failed to read config.json for pool settings: %s", exc)
    return ..., cycle_day, ...
```
`project_breakdown.py` needs only `billing_cycle_start_day`. Extract it with the same validation guard and `logger.warning` style.

**Billing cycle start derivation** (pool_state_manager.py lines 131-152, `_derive_billing_cycle_start`):
```python
def _derive_billing_cycle_start(cycle_day: int) -> date:
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
```
Import or replicate this helper exactly — do not rewrite the month-wrap logic.

**Public factory function signature** (pool_state_manager.py lines 222-240):
```python
def compute_pool_state(
    blocks: list,
    threshold_state,
    config_dir: Optional[Path] = None,
) -> "PoolState":
    """...
    Args:
        ...
    Returns:
        PoolState frozen dataclass ...
    """
    if config_dir is None:
        config_dir = _DEFAULT_CONFIG_DIR
```
New function signature:
```python
def compute_project_breakdown(
    data_path: Optional[Path] = None,
    config_dir: Optional[Path] = None,
) -> "ProjectBreakdown":
    if data_path is None:
        data_path = _DEFAULT_DATA_PATH
    if config_dir is None:
        config_dir = _DEFAULT_CONFIG_DIR
```

**JSONL file iteration + slug extraction** (data/reader.py lines 195-200, `_find_jsonl_files`):
```python
def _find_jsonl_files(data_path: Path) -> List[Path]:
    if not data_path.exists():
        logger.warning("Data path does not exist: %s", data_path)
        return []
    return list(data_path.rglob("*.jsonl"))
```
Usage: `file_path.parent.name` on each returned path gives the project slug (e.g. `C:-Users-justin-rhoda-token-tracker`). Display name = `slug.split("-")[-1]` per D-01.

**Deduplication — MUST reuse, do not copy** (data/reader.py lines 40-74, `_deduplicate_entries`):
```python
from claude_monitor.data.reader import _deduplicate_entries
```
Do NOT copy the deduplication logic. Import the private function directly. This is explicitly required by D-12 and the CONTEXT.md canonical refs.

**Token extraction from raw JSONL entry** (data/reader.py lines 226-247, `_process_single_file`):
```python
raw_parsed: List[Dict[str, Any]] = []
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

deduped_parsed = _deduplicate_entries(raw_parsed)
```
For token counting in `compute_project_breakdown`, after deduplication, extract:
```python
usage = entry.get("message", {}).get("usage", {})
total = (
    usage.get("input_tokens", 0)
    + usage.get("output_tokens", 0)
    + usage.get("cache_creation_input_tokens", 0)
    + usage.get("cache_read_input_tokens", 0)
)
```
This matches the `TokenCounts.total_tokens` definition in `core/models.py` lines 45-52.

**PermissionError handling** (data/reader.py lines 272-281):
```python
except PermissionError:
    # WinError 32: Claude Code holds a write lock on the active session file.
    logger.warning(
        "Permission denied reading %s — file locked by another process (active session)",
        file_path,
    )
    return [], None
```
Apply the same try/except PermissionError skip pattern for each file in `compute_project_breakdown`.

**Timestamp filtering for "today" scope** (D-16):
```python
from datetime import datetime, timezone
now_utc = datetime.now(timezone.utc)
today_date = now_utc.date()
# entry is from "today" if:
ts_str = entry.get("timestamp", "")
ts = datetime.fromisoformat(ts_str)
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=timezone.utc)
if ts.date() == today_date:
    ...
```

**Frozen dataclass construction + return** (pool_state_manager.py lines 307-314):
```python
result = PoolState(
    pool_size_usd=pool_size_usd,
    pool_spend_usd=pool_spend_usd,
    ...
)
return result
```
New module closes with:
```python
return ProjectBreakdown(
    today=today_top5,
    billing_month=month_top5,
    as_of=datetime.now(timezone.utc),
)
```

---

### `monitoring/orchestrator.py` — add `project_breakdown` to `monitoring_data`

**Analog:** `monitoring/orchestrator.py`, lines 1-16 (imports block) and lines 203-216 (`monitoring_data` dict)

**Import addition pattern** (lines 9-11, how prior phases added their imports):
```python
from claude_monitor.core.threshold_manager import ThresholdState, get_threshold
from claude_monitor.core.pool_state_manager import PoolState, compute_pool_state
```
New import to add in the same block:
```python
from claude_monitor.core.project_breakdown import ProjectBreakdown, compute_project_breakdown
```

**Call site pattern** (lines 186-212, `_fetch_and_process_data`):
```python
# Phase 3: compute pool state (pool spend, billing period, persistence)
pool_state: PoolState = compute_pool_state(blocks, threshold_state)

# Prepare monitoring data
monitoring_data: Dict[str, Any] = {
    "data": data,
    "token_limit": token_limit,
    "threshold_state": threshold_state,
    "pool_state": pool_state,              # Phase 3 NEW
    "web_usage": self._web_poller.get_web_usage() if self._web_poller else None,
    "last_web_sync": self._web_poller.get_last_sync_time() if self._web_poller else None,
    "args": self._args,
    "session_id": self.session_monitor.current_session_id,
    "session_count": self.session_monitor.session_count,
}
```
New call and dict key to insert after the `pool_state` line:
```python
# Phase 6: compute per-project token breakdown from local JSONL files
project_breakdown: ProjectBreakdown = compute_project_breakdown()

monitoring_data: Dict[str, Any] = {
    ...
    "pool_state": pool_state,
    "project_breakdown": project_breakdown,   # Phase 6 NEW
    "web_usage": ...,
    ...
}
```
`compute_project_breakdown()` takes no required args when defaults are correct. The `data_path` from `self.data_manager` may optionally be passed if the orchestrator was constructed with a non-default `data_path`.

---

### `ui/session_display.py` — layout restructure + per-project rendering

**Analog:** `ui/session_display.py` — the `custom`/`pro`/`max5`/`max20` branch of `format_active_session_screen` (lines 189-396)

**kwargs.get pattern for optional state** (lines 272, 330, 372):
```python
threshold_state = kwargs.get("threshold_state")
pool_state = kwargs.get("pool_state")
web_usage = kwargs.get("web_usage")
```
New retrieval follows identically:
```python
project_breakdown = kwargs.get("project_breakdown")
```

**Separator pattern** (lines 231, 253, 274, 336, 374):
```python
screen_buffer.append(f"[separator]{'─' * 60}[/]")
```
Per-project section uses one separator block shared by both columns (D-05 / specifics).

**Guard pattern before rendering an optional section** (lines 330-335):
```python
pool_state = kwargs.get("pool_state")
if (
    pool_state is not None
    and threshold_state is not None
    and threshold_state.status != "calibrating"
):
    screen_buffer.append(f"[separator]{'─' * 60}[/]")
    ...
```
Per-project guard (D-14):
```python
project_breakdown = kwargs.get("project_breakdown")
if project_breakdown is not None and (project_breakdown.today or project_breakdown.billing_month):
    screen_buffer.append(f"[separator]{'─' * 60}[/]")
    # render side-by-side columns here
```

**Rich markup style** (lines 339-369 — consistent inline markup):
```python
screen_buffer.append(
    f"🏦 [value]Pool spent:[/]   est. ${pool_state.pool_spend_usd:.2f} / ${pool_state.pool_size_usd:.2f}"
)
```
Per-project rows use the same `[value]...[/]` and `[dim]...[/]` tags. Column headers:
```python
f"📂 [value]Today (est.)[/]"
f"📂 [value]This month (est.)[/]"
```

**Side-by-side column construction** — no exact prior analog. Suggested approach using fixed column widths (Claude's discretion per CONTEXT.md):
```python
# Build left and right column lines independently, then zip
left_lines = [f"📂 [value]Today (est.)[/]"]
right_lines = [f"📂 [value]This month (est.)[/]"]
for (name, toks) in project_breakdown.today[:5]:
    left_lines.append(f"  {name:<22} {_fmt_tokens(toks)}")
for (name, toks) in project_breakdown.billing_month[:5]:
    right_lines.append(f"  {name:<22} {_fmt_tokens(toks)}")
# Pad shorter list to match
while len(left_lines) < len(right_lines):
    left_lines.append("")
while len(right_lines) < len(left_lines):
    right_lines.append("")
col_width = 32
for left, right in zip(left_lines, right_lines):
    screen_buffer.append(f"{left:<{col_width}}{right}")
```

**D-07: Rows to REMOVE** from the `custom`/`pro`/`max5`/`max20` branch (lines 206-245):
- Lines 210-213: `💰 Cost Usage` progress bar block
- Lines 215-220: `📊 Token Usage` progress bar block
- Lines 222-231: `📨 Messages Usage` progress bar block
- Lines 232-245: `⏱️ Time to Reset` progress bar block

**D-08: Rows to MOVE** — currently at lines 247-268 (`🤖 Model Distribution`, `🔥 Burn Rate`, `💲 Cost Rate`):
```python
if per_model_stats:
    model_bar = self.model_usage.render(per_model_stats)
    screen_buffer.append(f"🤖 [value]Model Distribution:[/]   {model_bar}")
else:
    model_bar = self.model_usage.render({})
    screen_buffer.append(f"🤖 [value]Model Distribution:[/]   {model_bar}")
screen_buffer.append(f"[separator]{'─' * 60}[/]")

velocity_emoji = VelocityIndicator.get_velocity_emoji(burn_rate)
screen_buffer.append(
    f"🔥 [value]Burn Rate:[/]              [warning]{burn_rate:.1f}[/] [dim]tokens/min[/] {velocity_emoji}"
)

cost_per_min = ...
screen_buffer.append(
    f"💲 [value]Cost Rate:[/]              {cost_per_min_display} [dim]$/min[/]"
)
```
Move these three rows to AFTER the web_usage block (after line 396 in current code, after `Last web sync` row), per D-09 layout order.

**D-09 new layout insertion order** for the `custom` branch:
```
1. header_manager.create_header(plan, timezone)          ← unchanged
2. "Session-Based Dynamic Limits" header                 ← unchanged (custom only)
3. separator
4. Phase 2 threshold rows                                ← unchanged
5. separator (inside phase 2 block)
6. Phase 3 pool rows                                     ← unchanged structure
7. separator (start of Phase 6 block)                    ← NEW
8. Per-project side-by-side columns (Phase 6)            ← NEW
9. separator (start of Phase 4 block)
10. Phase 4 web_usage rows (Utilization, Resets in, Last web sync)
11. Model Distribution                                   ← MOVED here
12. Burn Rate                                            ← MOVED here
13. Cost Rate                                            ← MOVED here
14. separator
15. Predictions block                                    ← unchanged
16. Notifications                                        ← unchanged
17. Footer                                               ← unchanged
```

---

## Shared Patterns

### Frozen Dataclass Convention
**Source:** `core/models.py` lines 114-131 (`WebUsageData`), `core/pool_state_manager.py` lines 28-38 (`PoolState`)
**Apply to:** `ProjectBreakdown` in `core/models.py`
```python
@dataclass(frozen=True)
class MyState:
    field_a: type
    field_b: Optional[type]
```
All new state objects are frozen dataclasses. No `field(default_factory=...)` unless a mutable default is needed (frozen dataclasses cannot have mutable defaults).

### Config Read Pattern
**Source:** `core/pool_state_manager.py` lines 59-128 (`_read_pool_config`)
**Apply to:** `core/project_breakdown.py` internal config helper
```python
config_file = config_dir / "config.json"
if not config_file.exists():
    return defaults
try:
    with open(config_file, encoding="utf-8") as f:
        data = json.load(f)
    raw_day = data.get("billing_cycle_start_day")
    if isinstance(raw_day, int) and 1 <= raw_day <= 28:
        cycle_day = raw_day
    elif raw_day is not None:
        logger.warning("config.json: billing_cycle_start_day=%r is not int 1-28 — using default 1", raw_day)
except Exception as exc:
    logger.warning("Failed to read config.json: %s", exc)
```

### Rich Markup Style
**Source:** `ui/session_display.py` lines 339-396
**Apply to:** all new rows in `format_active_session_screen`
- Labels: `[value]Label:[/]`
- Numbers/values: `[value]{n}[/]` or `[warning]{n}[/]`
- Dimmed context: `[dim]text[/]`
- Errors: `[error]text[/]`
- Success: `[success]text[/]`
- Separators: `f"[separator]{'─' * 60}[/]"`

### PermissionError / file-locked Skip
**Source:** `data/reader.py` lines 272-281
**Apply to:** `core/project_breakdown.py` file reading loop
```python
except PermissionError:
    logger.warning(
        "Permission denied reading %s — file locked by another process (active session)",
        file_path,
    )
    continue  # skip this file, not a fatal error
```

### JSONL File Open Pattern
**Source:** `data/reader.py` lines 226-237
**Apply to:** `core/project_breakdown.py`
```python
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
```
Use `encoding="utf-8-sig"` (not `utf-8`) — this strips the Windows BOM that Claude Code sometimes writes.

### kwargs.get Optional State Pattern
**Source:** `ui/session_display.py` lines 272, 330, 372
**Apply to:** `project_breakdown` retrieval in `format_active_session_screen`
```python
project_breakdown = kwargs.get("project_breakdown")
```
Always use `kwargs.get("key")` — never positional injection — for all new optional state passed to the display function.

---

## No Analog Found

All files have close analogs. No new patterns require RESEARCH.md fallback.

---

## Metadata

**Analog search scope:** `core/`, `data/`, `monitoring/`, `ui/`
**Files scanned:** 5 (models.py, pool_state_manager.py, reader.py, orchestrator.py, session_display.py)
**Pattern extraction date:** 2026-05-19
