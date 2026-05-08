# Stack Research: Claude Token Tracker (Windows Fork)

**Project:** Fork of Claude-Code-Usage-Monitor for Windows + company plan overage tracking
**Researched:** 2026-05-07
**Source project version:** v3.1.0 (7.9k stars, 401 forks)

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime | Source targets >=3.9; 3.11 removes the `tomli` shim and is faster. 3.12/3.13 also fine. |
| rich | >=13.7.0 (current: 14.1.0) | Terminal UI — panels, tables, live display | Already used by upstream; mature Windows support in new Windows Terminal |
| pydantic | >=2.0.0 | Data validation for parsed JSONL entries | Already upstream; v2 is significantly faster than v1 |
| numpy | >=1.21.0 | P90 calculation for overage threshold detection | Already upstream; overkill if you want fewer deps — `statistics.quantiles` from stdlib is sufficient for simple P90 |
| pyyaml | >=6.0 | Config file (thresholds, pool size) | Already upstream |
| pytz | >=2023.3 | Timezone-aware datetime handling | Already upstream; `zoneinfo` (stdlib, 3.9+) is the modern alternative but pytz avoids friction |
| tzdata | Latest | Windows timezone database | **Windows-specific required dep** — pytz on Windows needs this because Windows does not ship the IANA tz database |

### Build / Dev Tooling

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| uv | Latest (0.5+) | Virtual env, dependency management, editable install | 10-100x faster than pip; handles pyproject.toml natively; single-binary install on Windows via PowerShell |
| pyproject.toml | PEP 517/518 | Project metadata, deps, entry points | Already the upstream format; do not add requirements.txt |

### No New Dependencies Needed

The upstream stack already covers everything for the core fork. The only additions for the overage feature:
- `statistics.quantiles` from stdlib (no install needed) OR keep numpy for P90 — your choice.
- A `config.yaml` key for `overage_pool_usd: 500` and `overage_threshold_percentile: 90`.

---

## Windows Path Handling

### What the Upstream Code Does

The upstream reader uses:

```python
data_path = Path(data_path if data_path else "~/.claude/projects").expanduser()
```

This is **already cross-platform correct**. `Path("~/.claude/projects").expanduser()` resolves to `C:\Users\<name>\.claude\projects` on Windows because `pathlib.Path.expanduser()` uses `USERPROFILE` then `HOMEPATH+HOMEDRIVE` on Windows, in that order.

**Verdict:** The path logic works on Windows as-is — you do not need to rewrite it.

### Where You Must Be Careful

1. **`Path.home()` is more reliable than `expanduser("~")` on Windows.** The `Path.home()` class method uses the Windows API directly; `expanduser` relies on environment variables that can be wrong in domain-joined enterprise environments. For your fork, prefer:

   ```python
   # Preferred — uses Windows API, not env vars
   claude_dir = Path.home() / ".claude" / "projects"
   
   # Also acceptable — upstream approach, works in 99% of cases
   claude_dir = Path("~/.claude/projects").expanduser()
   ```

2. **Enterprise roaming profiles.** On Windows 11 Enterprise with domain accounts, `USERPROFILE` may point to a network share (`\\server\users\jrhoda`) while the actual `.claude` directory is in the local profile (`C:\Users\justin.rhoda`). If the tool shows "no data found," fall back to `os.environ.get("LOCALAPPDATA", "").replace("\\AppData\\Local", "")` or prompt the user to set `CLAUDE_DATA_DIR`.

3. **Forward vs back slashes.** `pathlib.Path` handles this automatically. Never hardcode `\\` separators. Always use `/` in `Path()` constructors or the `/` operator.

4. **MAX_PATH (260-char limit).** Not a concern for `.claude/projects` paths, but note that Windows 11 allows opting out via Group Policy. Not actionable for this tool.

5. **JSONL glob patterns.** The upstream likely uses `Path.glob("**/*.jsonl")`. This works on Windows without modification.

### Recommended Pattern for This Fork

```python
from pathlib import Path
import os

def get_claude_projects_dir() -> Path:
    """Resolve .claude/projects in a Windows-safe way."""
    # Allow explicit override first
    env_override = os.environ.get("CLAUDE_DATA_DIR")
    if env_override:
        return Path(env_override)
    
    # Path.home() is more reliable than expanduser on domain-joined Windows
    return Path.home() / ".claude" / "projects"
```

---

## Windows Terminal Rendering (Rich)

### Terminal Tier Support

| Terminal | Color Support | Live Display | Emoji | Notes |
|----------|--------------|--------------|-------|-------|
| Windows Terminal (new, default in Win 11) | True color (24-bit) | Works | Unicode 9+ | Best option; recommend users run here |
| PowerShell 7 in Windows Terminal | True color | Works | Unicode 9+ | Same as above |
| PowerShell 5 (legacy, `powershell.exe`) | 16 colors | Works with issues | Limited | Acceptable, no true color |
| cmd.exe (classic) | 16 colors | Works with issues | Limited | Falls back gracefully |
| VS Code integrated terminal | True color | Works | Works | Rich auto-detects |
| Git Bash (MSYS2) | True color | Broken — see below | Limited | Avoid for Live/Progress |

### Known Issues and Fixes

**Issue 1: Spinner/Live display scrolls instead of updating in-place (Git Bash and some CMD contexts)**
- Root cause: The terminal does not support ANSI cursor-up sequences (`\033[A`), so Rich cannot erase the previous frame.
- Fix: Run in Windows Terminal or PowerShell. If you must support Git Bash, disable the `Live` refresh and use plain `print()` with a refresh timer instead.
- GitHub issues: [#1320](https://github.com/Textualize/rich/issues/1320), [#2499](https://github.com/Textualize/rich/issues/2499)

**Issue 2: Live view flickering when new log entries arrive**
- Root cause: Windows Terminal's hardware rendering path.
- Fix: Use `refresh_per_second=4` (not higher) on `rich.live.Live`. Lower refresh rate reduces flicker visibly.
- GitHub issue: [#1024](https://github.com/Textualize/rich/issues/1024)

**Issue 3: UnicodeEncodeError on Windows with certain box-drawing characters or emoji**
- Root cause: Legacy cp1252/cp850 console encoding.
- Fix: Add this near the top of `__main__.py`:
  ```python
  import sys, io
  if sys.platform == "win32":
      sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
      sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
  ```
  Or set `PYTHONUTF8=1` environment variable. Python 3.15+ will make UTF-8 mode the default.
- GitHub issue: [#2411](https://github.com/Textualize/rich/issues/2411)

**Issue 4: `force_terminal` needed when stdout is redirected (e.g., piped to a log file)**
- Fix: The upstream likely detects this already. If not, use `Console(force_terminal=True)` only when you know you're in an interactive context. Use `Console(no_color=True)` for plain output when piped.

**Issue 5: Emoji width alignment breaks Table/Panel borders on some fonts**
- Root cause: Terminals disagree on emoji character widths.
- Fix: Set `UNICODE_VERSION=9.0` environment variable (Rich respects this). Stick to ASCII box-drawing characters for borders in the dashboard if alignment is critical. Avoid emoji in column headers.

### Recommended Console Setup for This Fork

```python
import os
from rich.console import Console

# Use Windows Terminal if available; degrade gracefully elsewhere
console = Console(
    highlight=False,         # avoid spurious color on numbers/paths
    emoji=False,             # avoid width alignment bugs in tables
    force_terminal=None,     # let Rich auto-detect (correct behavior)
)
```

---

## Forking Approach

### Recommended: git clone + uv editable install

```powershell
# 1. Install uv (one-time, Windows)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Clone the upstream into a subdirectory of your fork repo
git clone https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor upstream-reference
# (keep this read-only for diffing; do NOT develop in it)

# 3. In your fork repo root (token.tracker/)
uv init --bare          # creates pyproject.toml if not already present
uv venv                 # creates .venv
uv pip install -e .     # editable install — code changes take effect immediately

# 4. Run the tool
uv run claude-monitor   # or whichever entry point you name
```

### pyproject.toml Minimal Starting Point

Copy the upstream `pyproject.toml` and:
- Change `name` to `token-tracker` (or your choice)
- Change `version` to `0.1.0`
- Add `tzdata` to dependencies (Windows tz database)
- Keep all upstream entry points or rename to avoid conflict with the upstream if both are installed
- Remove `numpy` if you use `statistics.quantiles` for P90

### Do NOT do This

- Do not `pip install claude-code-usage-monitor` and then try to patch it. The installed package is in site-packages and not editable.
- Do not add a `requirements.txt` alongside `pyproject.toml` — it creates dependency duplication drift.
- Do not use `python setup.py develop` — this is the pre-PEP517 deprecated approach.

### Tracking Upstream Changes

```bash
# Add upstream as a remote to pull in future fixes
git remote add upstream https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor
git fetch upstream
git log upstream/main --oneline  # see what changed
```

---

## Anthropic Pricing (current as of 2026-05-07)

Source: [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing)

All prices in USD per million tokens (MTok).

| Model | Input | Cache Write (5 min) | Cache Write (1 hr) | Cache Read (hit) | Output |
|-------|-------|--------------------|--------------------|-----------------|--------|
| Claude Opus 4.7 | $5.00 | $6.25 | $10.00 | $0.50 | $25.00 |
| Claude Opus 4.6 | $5.00 | $6.25 | $10.00 | $0.50 | $25.00 |
| Claude Opus 4.5 | $5.00 | $6.25 | $10.00 | $0.50 | $25.00 |
| Claude Sonnet 4.6 | $3.00 | $3.75 | $6.00 | $0.30 | $15.00 |
| Claude Sonnet 4.5 | $3.00 | $3.75 | $6.00 | $0.30 | $15.00 |
| Claude Sonnet 4 | $3.00 | $3.75 | $6.00 | $0.30 | $15.00 |
| Claude Sonnet 3.7 (deprecated) | $3.00 | $3.75 | $6.00 | $0.30 | $15.00 |
| Claude Haiku 4.5 | $1.00 | $1.25 | $2.00 | $0.10 | $5.00 |
| Claude Haiku 3.5 | $0.80 | $1.00 | $1.60 | $0.08 | $4.00 |
| Claude Haiku 3 | $0.25 | $0.30 | $0.50 | $0.03 | $1.25 |

### Notes for Cost Calculation

- **Cache write tokens** appear in JSONL as `cache_creation_input_tokens`. The JSONL does NOT tell you which cache duration (5 min vs 1 hr) was used — you cannot distinguish them from the logs. Use the 5-minute write price ($1.25x multiplier over base input) as a conservative approximation.
- **Cache read tokens** appear as `cache_read_input_tokens`. Price is 0.1x base input.
- **Regular input tokens** appear as `input_tokens` (subtract cache tokens if present).
- **Output tokens** appear as `output_tokens`.

### Cost Calculation Formula per JSONL Entry

```python
def compute_cost(entry: dict, model_prices: dict) -> float:
    model = entry.get("model", "")
    prices = model_prices.get(model, model_prices["default"])
    
    raw_input = entry.get("input_tokens", 0) - entry.get("cache_creation_input_tokens", 0) - entry.get("cache_read_input_tokens", 0)
    cache_write = entry.get("cache_creation_input_tokens", 0)
    cache_read = entry.get("cache_read_input_tokens", 0)
    output = entry.get("output_tokens", 0)
    
    cost = (
        raw_input * prices["input"] +
        cache_write * prices["cache_write"] +
        cache_read * prices["cache_read"] +
        output * prices["output"]
    ) / 1_000_000
    return cost
```

### Opus 4.7 Tokenizer Warning

Opus 4.7 ships with a new tokenizer that produces up to 35% more tokens for the same input text. If you see unexpectedly high token counts for Opus 4.7 sessions, this is by design, not a bug.

---

## What NOT to Use / Watch Out For

### Deprecated Approaches

| Anti-Pattern | Why Avoid | Use Instead |
|--------------|-----------|-------------|
| `os.path.join("~", ".claude", "projects")` without `expanduser` | Does not resolve `~` | `Path.home() / ".claude" / "projects"` |
| `hardcoded "C:\\Users\\username\\.claude"` | Obviously user-specific, breaks on any other machine | `Path.home()` |
| `python setup.py develop` | Deprecated pre-PEP517 editable install | `uv pip install -e .` |
| `requirements.txt` alongside `pyproject.toml` | Drift between the two files | Put all deps in `pyproject.toml` only |
| `pip install -e .` directly (without uv) | Works but slower; no lockfile | `uv pip install -e .` + `uv lock` |
| `os.environ["HOME"]` on Windows | `HOME` is not a standard Windows env var; may be unset | `Path.home()` |
| `rich.Console(force_terminal=True)` unconditionally | Breaks piped output, makes logs unreadable | Only set if explicitly in interactive mode |
| High `refresh_per_second` on `Live` (e.g., 30) | Causes visible flicker in Windows Terminal | Use 4 or lower |
| Emoji in table column headers | Width alignment breaks borders on Windows fonts | Use ASCII text labels |
| `numpy` for a single P90 calculation | Heavy dependency for trivial stats | `statistics.quantiles(data, n=10)[8]` |

### Pydantic v1 / v2 Compatibility

The upstream requires pydantic >=2.0.0. Do not backslide to v1. If you see `from pydantic import validator` in any code you copy, replace with `@field_validator` (v2 API).

### Python Version Floor

Do not target Python 3.8. It reached end-of-life October 2024. The upstream targets 3.9+; recommend 3.11+ for your fork to get `tomllib` in stdlib and better `zoneinfo` support.

---

## Confidence Levels

| Area | Confidence | Reasoning |
|------|------------|-----------|
| Upstream path logic | HIGH | Verified by reading actual source code from the repo — uses `Path(...).expanduser()` |
| `Path.home()` preference over `expanduser` on Windows domain accounts | MEDIUM | CPython bug tracker confirms env-var dependency issue; no direct Windows Enterprise test data available |
| Rich Windows Terminal compatibility | HIGH | Verified via official Rich docs + confirmed GitHub issues with specific issue numbers |
| Rich spinner/Live scroll bug | HIGH | Multiple confirmed open GitHub issues (#1320, #2499, #1024) with reproduction steps |
| Anthropic pricing table | HIGH | Fetched directly from official pricing page (platform.claude.com) |
| `tzdata` requirement on Windows | HIGH | Well-documented pytz behavior; pytz docs explicitly state this |
| uv editable install workflow | HIGH | Official uv docs + pydevtools handbook |
| P90 via `statistics.quantiles` as numpy replacement | HIGH | Python 3.10 stdlib, no external verification needed |
| Opus 4.7 tokenizer 35% increase | HIGH | Noted explicitly on official pricing page |

---

## Sources

- [pathlib official docs](https://docs.python.org/3/library/pathlib.html)
- [CPython issue #80445: os.path.expanduser should not use HOME on Windows](https://bugs.python.org/issue36264)
- [Rich official docs — Console API](https://rich.readthedocs.io/en/stable/console.html)
- [Rich GitHub — spinner scrolls on Windows #1320](https://github.com/Textualize/rich/issues/1320)
- [Rich GitHub — spinner scrolls awkwardly #2499](https://github.com/Textualize/rich/issues/2499)
- [Rich GitHub — Live view flickering on Windows #1024](https://github.com/Textualize/rich/issues/1024)
- [Rich GitHub — UnicodeEncodeError on Windows #2411](https://github.com/Textualize/rich/issues/2411)
- [Anthropic pricing page (official)](https://platform.claude.com/docs/en/about-claude/pricing)
- [uv official docs — editable installs](https://docs.astral.sh/uv/pip/packages/)
- [uv official docs — working on projects](https://docs.astral.sh/uv/guides/projects/)
- [Claude Code JSONL path — ccusage reference impl](https://github.com/ryoppippi/ccusage)
- [Claude-Code-Usage-Monitor upstream repo](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor)
