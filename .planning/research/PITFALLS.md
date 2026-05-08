# Pitfalls: Windows Fork of Python Terminal Tool

**Domain:** Porting Python CLI / Rich terminal UI (Claude-Code-Usage-Monitor) from Unix to Windows 11
**Researched:** 2026-05-07

---

## Path Handling Pitfalls

### CRITICAL — Hardcoded Unix Log Path

**What goes wrong:** The upstream tool uses `~/.claude/projects/` (or `~/.config/claude`) to discover JSONL files. On Windows, `~` expands via `USERPROFILE`, not `HOME`. The actual Claude Code log path on Windows is `%APPDATA%\.claude\projects\` (i.e., `C:\Users\<name>\AppData\Roaming\.claude\projects\`). A naively ported `Path("~/.claude/projects").expanduser()` will resolve to `C:\Users\<name>\.claude\projects\` — the wrong location — and silently find zero files.

**Warning sign:** Tool starts but shows no sessions and no error. Log search returns empty; `APPDATA` directory is never checked.

**Prevention:**
1. Use `Path.home() / "AppData" / "Roaming" / ".claude" / "projects"` on Windows, with a `sys.platform` branch.
2. Alternatively, respect the `CLAUDE_CONFIG_DIR` environment variable as an escape hatch, and document the Windows default prominently.
3. Never hardcode the path as a string literal; always construct it through `pathlib.Path`.

**Most likely phase:** Phase 1 (initial port / smoke test). Presents as "no data found" rather than a crash, so easy to miss.

---

### CRITICAL — String Concatenation Instead of pathlib

**What goes wrong:** Code doing `base_path + "/" + subdir` or `f"{home}/.claude/{session}"` produces valid paths on Unix but broken paths on Windows (forward slash inside a string component is not split by `os.path.join`, creating mixed-slash paths like `C:\Users\name/.claude/projects`). Most Python `open()` calls tolerate this, but glob patterns and subprocess calls do not.

**Warning sign:** Unit tests pass on the developer's Mac but subprocess calls or glob patterns silently fail on Windows. `str(path)` shows mixed `\` and `/`.

**Prevention:** Replace every path string concatenation with `pathlib.Path` `/` operator. Use `path.as_posix()` only when passing to tools that explicitly require POSIX strings (git, etc.).

**Most likely phase:** Phase 1, surfaces again in Phase 3 if subprocess calls are added for git integration.

---

### MODERATE — MAX_PATH (260-character limit)

**What goes wrong:** Deep project structures (long org names, long session UUIDs) can exceed the legacy 260-character Windows path limit. `open()` raises `FileNotFoundError` with no hint about path length being the cause.

**Warning sign:** Works on shallow paths, fails on deeply nested ones. Error is `FileNotFoundError` or `OSError` with no obvious explanation.

**Prevention:** Enable long paths via `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled = 1` in your installer or README, and document it as a prerequisite. Python 3.6+ respects this registry key automatically.

**Most likely phase:** Phase 2 (file discovery), unlikely to surface until real user data is present.

---

### MINOR — Case Sensitivity

**What goes wrong:** NTFS is case-insensitive by default. Code doing `path.lower()` comparisons for deduplication works on Windows but will break if the tool is later run on a case-sensitive volume (WSL, Docker). More practically: glob patterns like `*.JSONL` vs `*.jsonl` behave differently.

**Prevention:** Always use `.lower()` or `.casefold()` consistently when comparing filenames; use `Path.glob("*.jsonl")` (lowercase) as the canonical pattern.

**Most likely phase:** Phase 1.

---

## Rich Windows Rendering Pitfalls

### CRITICAL — ANSI/Color Support in cmd.exe and Older PowerShell

**What goes wrong:** Rich auto-detects the color system. In legacy `cmd.exe` (without Virtual Terminal Processing enabled), Rich falls back to 8 colors or plain text. The dashboard can render with no color at all, making progress bars and status indicators unreadable. Classic `cmd.exe` does not have VT100 enabled by default before Windows 10 1511.

**Warning sign:** Running `python -m rich` in `cmd.exe` shows `[bold]` as literal text, or colors render as garbled escape sequences.

**Prevention:**
- Target Windows Terminal as the documented runtime; call this out in the README.
- Programmatically enable VTP at startup via `ctypes` if running under `cmd.exe`:
  ```python
  import ctypes, sys
  if sys.platform == "win32":
      kernel32 = ctypes.windll.kernel32
      kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
  ```
- Do not rely on the `colorama` shim — Rich handles its own rendering pipeline and mixing colorama can cause double-escaping.

**Most likely phase:** Phase 1 (immediately visible when first running the port).

---

### CRITICAL — Terminal Width Auto-Detection Fallback

**What goes wrong:** Rich uses `shutil.get_terminal_size()` internally. There is a confirmed Rich bug (issue #3412) where on Windows, width detection only checks `STDOUT`. If the console is created against `STDERR` (common when stdout is redirected to a log), the auto-detected size falls back to `(80, 25)` regardless of actual window size. The dashboard then wraps incorrectly.

**Warning sign:** Dashboard wraps at 80 columns even in a wide Windows Terminal window. Symptom disappears when stdout is not redirected.

**Prevention:** When constructing `Console`, pass `width=shutil.get_terminal_size().columns` explicitly rather than relying on auto-detection. Re-query on `SIGWINCH` equivalent (Windows Terminal sends `WM_SIZE`; polling every refresh cycle is the pragmatic fallback).

**Most likely phase:** Phase 2 (Live display / dashboard rendering).

---

### MODERATE — Unicode Emoji and Box-Drawing Characters

**What goes wrong:** Rich uses Unicode box-drawing characters and emoji for progress bars and status icons. Windows Terminal (modern) handles these correctly. `cmd.exe` and older PowerShell consoles running in legacy raster fonts (Courier New) will render box-drawing as `?` or mojibake. Emoji (e.g., warning signs, clocks) fail entirely in non-UTF-8 codepages.

**Warning sign:** Box characters appear as `?` or garbage; code page is not 65001 (`chcp` returns 850 or similar).

**Prevention:**
- At startup, call `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` on Windows.
- Force the console codepage: `os.system('chcp 65001 > nul')` (acceptable for a terminal tool).
- Use only ASCII fallbacks for critical status indicators (e.g., `[OK]` alongside checkmark emoji) so the tool degrades gracefully.
- Document "use Windows Terminal with Cascadia Code or Consolas" as the recommended setup.

**Most likely phase:** Phase 2, also Phase 3 if overage indicators use colored emoji.

---

### MINOR — Rich Live Display Flicker in Windows Terminal

**What goes wrong:** Rich's `Live` context manager uses ANSI cursor movement to update in place. In some Windows Terminal builds, rapid updates (< 100 ms refresh) produce visible flicker because the Windows conPTY layer buffers differently than a native VT terminal.

**Prevention:** Set `refresh_per_second=4` (default is 4; do not go higher than 10 in the Windows-targeted build). Add a minimum sleep of 250 ms between dashboard updates.

**Most likely phase:** Phase 2.

---

## JSONL Parsing Pitfalls

### CRITICAL — Streaming Placeholder Token Values (requestId Deduplication)

**What goes wrong:** Claude Code writes JSONL entries *during* streaming, not after request completion. A single API request generates 2-10 JSONL entries sharing the same `requestId`. The first (and most) entries have `usage.input_tokens = 1` (a placeholder). The final entry has the true input count. Any parser that sums all entries without deduplicating by `requestId` will produce token counts that are 100-174x too high for input tokens and 10-17x too high for output tokens. Cache fields (`cache_creation_input_tokens`, `cache_read_input_tokens`) are set correctly from the start and do not need deduplication.

This is a confirmed upstream bug (GitHub issue #22686). The upstream monitor has its own deduplication logic — when forking, verify that logic is preserved exactly.

**Warning sign:** Displayed token totals are wildly higher than Anthropic Console billing figures. Cache-only sessions show reasonable numbers but mixed sessions are off.

**Prevention:**
- Group all JSONL entries by `requestId`; use only the entry with the highest `output_tokens` value (the final streaming chunk) or the entry where `stop_reason` is non-null.
- Add a sanity check: if computed total exceeds `5 * previous_total` within one refresh cycle, suspect a parse regression.
- Write a unit test with a known multi-entry JSONL fixture that asserts the correct deduplicated total.

**Most likely phase:** Phase 1 (data pipeline). Silent until compared against actual billing.

---

### CRITICAL — Windows File Sharing Violation (Claude Code Holds Write Lock)

**What goes wrong:** On Windows, `open()` acquires an exclusive lock by default. Claude Code holds a write handle on the active session's `.jsonl` file. A Python `open(path, 'r')` call from the monitor will raise `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.

Unix tools never encounter this because POSIX allows multiple simultaneous readers and writers on the same file descriptor.

**Warning sign:** `PermissionError` or `WinError 32` when the monitor tries to read the currently active session file. Works fine on files from completed sessions.

**Prevention:**
- Open with explicit sharing flags via `msvcrt` or `win32file`:
  ```python
  import msvcrt, os
  fd = os.open(path, os.O_RDONLY | os.O_BINARY)
  # msvcrt.locking is not needed for read-only; os.O_RDONLY allows shared read
  ```
  Or use the `win32file` API with `FILE_SHARE_READ | FILE_SHARE_WRITE`.
- Simpler alternative: wrap the read in a `try/except PermissionError` and skip the locked file for that refresh cycle, retrying next cycle.
- The skip-and-retry approach matches expected UX: the active session file updates continuously anyway.

**Most likely phase:** Phase 1 (file reading). Surfaces immediately on first live test.

---

### MODERATE — CRLF Line Endings in JSONL

**What goes wrong:** If any tool in the pipeline (git `autocrlf`, notepad, Windows text editors) touches the `.jsonl` files, lines may end in `\r\n` instead of `\n`. `json.loads(line)` will fail on lines ending in `\r` because `\r` is included in the string and JSON does not allow bare carriage returns outside strings.

**Warning sign:** `json.JSONDecodeError: Invalid control character` on lines that look visually correct.

**Prevention:** Always open JSONL files with `open(path, 'r', encoding='utf-8', newline='')` and strip each line: `line.strip()` before passing to `json.loads()`. Never open in binary mode and decode manually unless you also strip `\r`.

**Most likely phase:** Phase 1. Low probability if reading files written exclusively by Claude Code (which writes LF), but rises to HIGH probability once git touches the repo or anyone copies files between systems.

---

### MODERATE — Missing or Null Fields in Malformed Entries

**What goes wrong:** Claude Code occasionally writes truncated entries when the process is killed mid-write (power loss, `Ctrl+C`). The last line of a session file may be a partial JSON object. A `json.loads()` on a partial line raises `JSONDecodeError`. More subtly, valid JSON entries may be missing the `usage` field entirely (tool-use result entries have no usage data).

**Prevention:**
- Wrap every `json.loads()` in `try/except json.JSONDecodeError` and skip the line.
- After parsing, use `.get()` with defaults for all usage fields: `entry.get("message", {}).get("usage", {}).get("input_tokens", 0)`.
- Never use `entry["message"]["usage"]["input_tokens"]` — this is a crash waiting to happen.

**Most likely phase:** Phase 1.

---

### MINOR — UTF-8 BOM in Windows-Written Files

**What goes wrong:** Windows tools (Notepad, Excel, some editors) write UTF-8 files with a BOM (`\xef\xbb\xbf`). If a user's Claude Code config path contains a file touched by such a tool, `json.loads()` will fail on the first line with `Unexpected UTF-8 BOM`.

**Prevention:** Open files with `encoding='utf-8-sig'` instead of `encoding='utf-8'`. The `-sig` variant silently strips the BOM if present and is otherwise identical.

**Most likely phase:** Phase 1. Rare but infuriating when it occurs.

---

## Token Cost Calculation Pitfalls

### CRITICAL — Model Name String Matching Against Pricing Table

**What goes wrong:** The JSONL `model` field contains full versioned model strings like `claude-sonnet-4-5-20251022` or `claude-3-5-sonnet-20241022`. Pricing tables keyed on display names like `"claude-3-5-sonnet"` will miss unless the matching uses prefix/substring logic. New model releases (Sonnet 4.6, Haiku 4.5, Opus 4.7 as of 2026) will not appear in any hardcoded table written against 2024 model names. The result is a silent `$0.00` cost for unrecognized models.

**Warning sign:** Cost shows `$0.00` or unrealistically low for recent sessions. Logs show model strings that do not match any pricing table key.

**Prevention:**
- Key the pricing table on model *family* prefixes and match with `model_string.startswith(prefix)`, ordered from most-specific to least-specific (e.g., `"claude-opus-4"` before `"claude-opus"`).
- Add a fallback that logs a warning and uses a conservative "unknown model" rate rather than returning 0.
- Include a `PRICING_LAST_UPDATED` constant and surface a UI warning when the current date is more than 90 days past it.
- Current (2026) known families: `claude-opus-4` ($5/$25 per 1M), `claude-sonnet-4` ($3/$15), `claude-haiku-4` ($1/$5). Older families: `claude-3-5-sonnet` ($3/$15), `claude-3-haiku` ($0.25/$1.25).

**Most likely phase:** Phase 1 (pricing engine), re-surfaces every time Anthropic releases a model.

---

### CRITICAL — Cache Token Pricing Is Not the Same as Regular Token Pricing

**What goes wrong:** Cache tokens have different rates: `cache_creation_input_tokens` cost 1.25x the standard input rate; `cache_read_input_tokens` cost 0.1x the standard input rate. A parser that treats all token types at the standard input rate will produce costs that are 2-10x off in cache-heavy sessions. Claude Code sessions are extremely cache-heavy (issue #24147 shows cache reads consuming 99.93% of quota in some workflows).

**Warning sign:** Computed cost is consistently lower than actual Anthropic Console bill, with the gap growing the longer a session runs (more cache reads accumulate).

**Prevention:**
- Implement separate multipliers per token type:
  ```python
  cost = (input_tokens * input_rate
        + output_tokens * output_rate
        + cache_creation_tokens * input_rate * 1.25
        + cache_read_tokens * input_rate * 0.10)
  ```
- Verify against the official Anthropic pricing page; cache multipliers have not changed since 2024 but confirm before shipping.

**Most likely phase:** Phase 1. The bug is invisible without a real-session comparison.

---

### MODERATE — Floating Point Rounding in Cost Accumulation

**What goes wrong:** Accumulating `float` costs per-entry over thousands of JSONL lines accumulates rounding error. Displaying `$0.023999999` instead of `$0.024` is a cosmetic bug; the deeper risk is that threshold comparisons (`if total_cost >= budget_limit`) trigger slightly early or late due to float imprecision.

**Prevention:**
- Use `decimal.Decimal` for all cost accumulation, or accumulate integer token counts and convert to cost only at display time.
- For threshold comparisons, add a small epsilon: `if total_cost >= budget_limit - 0.0001`.
- Display costs with `f"${cost:.4f}"` (4 decimal places) — do not round to 2 places until final display.

**Most likely phase:** Phase 3 (overage pool indicator, where threshold comparisons matter).

---

### MODERATE — Off-By-One on Session Boundary (5-Hour Window)

**What goes wrong:** Claude Code's rate limit resets on a 5-hour rolling window. The upstream monitor infers the reset time from the timestamp of the oldest entry in the current window. If the boundary timestamp is included in both the expiring window and the new window (fence-post error), tokens are double-counted, making the "time to limit" projection too pessimistic.

**Prevention:** Use strictly-less-than comparisons for window boundaries: `entry_time >= window_start` (not `>`). Write a unit test with entries exactly at the boundary timestamp.

**Most likely phase:** Phase 2 (session window logic).

---

### MINOR — Timezone Handling for Reset Time Display

**What goes wrong:** JSONL timestamps are UTC ISO 8601. Displaying "resets in 2h 14m" requires converting to the user's local timezone. `datetime.utcnow()` is deprecated in Python 3.12+. Using naive datetimes and assuming local = UTC produces wrong reset times for non-UTC users.

**Prevention:** Use `datetime.now(timezone.utc)` throughout. Install `tzdata` as a dependency (already listed in the upstream's Windows requirements) and use `zoneinfo.ZoneInfo` for local time conversion. Never use `datetime.utcnow()`.

**Most likely phase:** Phase 2.

---

## Editable Install / Fork Setup Pitfalls

### CRITICAL — console_scripts Not on PATH After `pip install -e .`

**What goes wrong:** `pip install -e .` installs scripts to `<venv>\Scripts\` (Windows) or `~/.local/bin` (Unix). On Windows, if the virtual environment's `Scripts\` directory is not in `PATH`, commands like `claude-monitor` are not found. This is the most common first-run failure for Windows users of Python CLI tools.

**Warning sign:** `pip install -e .` completes with no errors, but `claude-monitor` (or your fork's command name) returns `command not found` / `is not recognized as an internal or external command`.

**Prevention:**
- Always instruct users to activate the venv before running: `.\venv\Scripts\activate` (PowerShell) or `venv\Scripts\activate.bat` (cmd).
- Alternatively, advise `python -m token_tracker` as a venv-safe invocation that always works.
- In your README, show Windows-specific PATH setup for user-level installs (no venv): `py -m site --user-site` → replace `site-packages` with `Scripts`.

**Most likely phase:** Phase 0 (developer setup), also Phase 4 (user documentation).

---

### CRITICAL — Editable Install Incompatibility with Binary Extensions / Legacy Mode

**What goes wrong:** If the upstream package uses a `setup.py` alongside `pyproject.toml`, `pip install -e .` on Windows may fail with `AttributeError: install_requires` or produce a broken install where the package is not importable. This is due to setuptools' new PEP 660 editable mode conflicting with legacy `setup.py develop`-style builds on Windows.

**Warning sign:** `import token_tracker` fails after `pip install -e .` with no error during install. Or install raises `error: legacy-install-failure`.

**Prevention:**
- Use the compat workaround for the development environment: `pip install -e . --config-settings editable_mode=compat`
- For a clean fork, migrate fully to `pyproject.toml` only (no `setup.py`) with `[build-system] requires = ["setuptools>=64"]` to get PEP 660 support.
- Add `SETUPTOOLS_ENABLE_FEATURES=legacy-editable` to the Windows dev setup instructions as a fallback.

**Most likely phase:** Phase 0 (developer setup). Blocks all development if not resolved immediately.

---

### MODERATE — Conflicting Package Name with Upstream on the Same Machine

**What goes wrong:** If both the upstream `claude-code-usage-monitor` and your fork are installed in the same Python environment, import resolution is undefined. The fork may silently import upstream code. `pip list` will show both with the same module name.

**Warning sign:** Code changes have no effect; the running process reports the upstream version number.

**Prevention:**
- Rename the Python package (the `name` in `pyproject.toml`) to something distinct, e.g., `token-tracker-enterprise`. Do this in Phase 0 before any other work.
- Always develop in a dedicated virtual environment that does not have the upstream installed.

**Most likely phase:** Phase 0.

---

### MINOR — Data Files Not Included in Editable Install

**What goes wrong:** If the project includes non-Python data files (themes, config templates, pricing JSON), these may not be accessible at runtime in editable mode because `importlib.resources` resolves paths differently for editable installs vs. installed packages.

**Prevention:** Use `importlib.resources.files(__package__) / "data" / "pricing.json"` (Python 3.9+) rather than `__file__`-relative paths. Test both editable and non-editable installs against the same data file access code.

**Most likely phase:** Phase 1, if pricing data is externalized to a JSON file.

---

## P90 Detection Pitfalls

### CRITICAL — Cold Start With Insufficient History (< 10 Sessions)

**What goes wrong:** P90 is meaningless with fewer than 10 data points. `numpy.percentile([500], 90)` returns `500` — the single observation — and the system interprets this as the "normal" limit. On first run or after clearing history, the P90 detector sees only 1-3 sessions and sets an artificially low (or high) dynamic limit, causing false-positive overage warnings or missed warnings throughout early use.

**Warning sign:** The overage pool indicator triggers on day 1 with only a single session in history. Or the indicator never triggers even during genuinely heavy usage in the first week.

**Prevention:**
- Enforce a minimum sample size (recommended: 10 sessions, 3 days of history) before activating P90-based limits.
- During the bootstrap period, display a "calibrating..." state rather than a threshold indicator.
- Persist session history to disk (`~/.token-tracker/history.json` on Windows: `%APPDATA%\token-tracker\history.json`) so history survives process restarts.

**Most likely phase:** Phase 3 (P90 / overage pool feature). First-use experience.

---

### CRITICAL — Outlier Sessions Permanently Skewing P90

**What goes wrong:** A single outlier session (e.g., a 4-hour deep-research session using 10x normal tokens) raises the P90 significantly. If the history window is unbounded, this outlier persists indefinitely, making the "normal" threshold too lenient and hiding future overages. Conversely, a one-time light-usage period (vacation) can make the threshold too strict.

**Warning sign:** P90 threshold drifts upward over months without genuine usage pattern change. Users report the overage indicator stops triggering despite clearly heavy sessions.

**Prevention:**
- Use a rolling window of the last 30 calendar days (or last 100 sessions, whichever is smaller) — not all-time history.
- Optionally apply a mild outlier filter: exclude sessions above P99 before computing P90 (compute P99 first, exclude, then recompute P90 on the remaining population).
- Display the current P90 value and the number of sessions it is based on in the UI so users can sanity-check it.

**Most likely phase:** Phase 3. Invisible until weeks of real usage accumulate.

---

### MODERATE — Stale History After Plan Tier Change

**What goes wrong:** A user upgrades from Pro to Max (or their company moves to a Team plan with a larger pool). Their historical P90 was calibrated against the old limit. The new plan allows higher usage, but the P90 threshold still reflects old conservative patterns. The overage indicator will never trigger even at 90% of the new, larger limit.

**Warning sign:** User upgrades plan; overage indicator becomes permanently silent.

**Prevention:**
- Detect plan-tier changes (e.g., when the JSONL-reported limit changes materially) and prompt the user to reset the P90 calibration window.
- Alternatively, expose a `/reset-calibration` CLI command or a config flag `--reset-p90-history`.

**Most likely phase:** Phase 3. Edge case but important for the company-plan overage pool feature specifically.

---

### MODERATE — Different Interpolation Methods Across Environments

**What goes wrong:** `numpy.percentile()`, `statistics.quantiles()`, and `pandas.quantile()` use different default interpolation methods (`linear`, `inclusive`/`exclusive`, `linear` respectively). On small samples (n < 30), these produce meaningfully different P90 values. If the implementation switches libraries between environments (e.g., numpy not installed → falls back to statistics), the threshold shifts invisibly.

**Prevention:** Pin to a single implementation. Recommend `numpy.percentile(data, 90, interpolation='linear')` and list numpy as a hard dependency. Do not use `statistics.quantiles()` for this feature — it requires `n >= 2` and produces coarser results.

**Most likely phase:** Phase 3.

---

### MINOR — P90 of What, Exactly?

**What goes wrong:** "P90 of token usage" is ambiguous: P90 of tokens-per-session? tokens-per-hour? tokens-per-day? tokens-per-5-hour-window? Using the wrong granularity produces a threshold that does not correspond to the rate limit being protected. Claude Code rate limits are per-5-hour-window, so a daily P90 is the wrong unit.

**Prevention:** Explicitly define P90 as the 90th percentile of *total tokens consumed in a 5-hour window* across recent history. Annotate the variable with a docstring stating this definition. Display the unit in the UI: "P90 limit: 142,000 tokens / 5-hour window."

**Most likely phase:** Phase 3 design / specification.

---

## Phase-Specific Warning Summary

| Phase | Topic | Highest-Risk Pitfall | Mitigation |
|-------|-------|----------------------|------------|
| 0 | Fork setup | Conflicting package name | Rename in `pyproject.toml` first |
| 0 | Dev environment | Editable install failure (PEP 660) | Use `editable_mode=compat` or pure `pyproject.toml` |
| 1 | File discovery | Wrong AppData path for JSONL logs | `sys.platform` branch to AppData path |
| 1 | File reading | `WinError 32` file sharing violation | `try/except PermissionError` + skip-and-retry |
| 1 | Token parsing | requestId deduplication (100x overcounts) | Deduplicate by requestId, use final entry only |
| 1 | Cost engine | Model name mismatch → $0 cost | Prefix-match pricing table + unknown-model warning |
| 1 | Cost engine | Cache tokens at wrong rate | Separate multipliers per token type |
| 2 | Dashboard | No color in cmd.exe | Enable VTP at startup via ctypes |
| 2 | Dashboard | Width auto-detection fallback (80 cols) | Pass explicit width to Console constructor |
| 2 | Dashboard | Unicode rendering in legacy terminals | `chcp 65001` + ASCII fallbacks |
| 2 | Session window | Off-by-one on 5-hour boundary | Strictly-less-than comparisons + unit test |
| 3 | P90 feature | Cold start with 1-3 sessions | Min 10 sessions before activating threshold |
| 3 | P90 feature | Outliers skewing threshold upward | Rolling 30-day window + P99 outlier exclusion |
| 3 | Overage pool | Plan tier change invalidates history | Detect limit change, prompt re-calibration |

---

## Confidence Levels

| Area | Confidence | Basis |
|------|------------|-------|
| Path handling (Windows AppData) | HIGH | Official Python docs + confirmed Claude Code log location from multiple tools |
| Rich Windows rendering (ANSI, width) | HIGH | Confirmed Rich GitHub issues #135, #1640, #3412 + official Rich docs |
| JSONL requestId deduplication bug | HIGH | Confirmed upstream GitHub issues #22686 and #5034 on anthropics/claude-code |
| Windows file sharing violation | HIGH | Confirmed Python discussion thread + WinError 32 documentation |
| Cache token pricing multipliers | HIGH | Official Anthropic pricing page + confirmed community analysis |
| Model name matching | MEDIUM | Inferred from observed model string format in JSONL + current pricing table; model names change with new releases |
| P90 cold start / outlier behavior | MEDIUM | Standard statistical practice; not project-specific documentation |
| Editable install / PEP 660 failure | MEDIUM | Confirmed setuptools GitHub issues; Windows-specific failure rate varies by Python version |
| P90 granularity (5-hour window) | MEDIUM | Inferred from Claude Code rate limit architecture; verify against actual limit reset behavior |
| Float rounding in cost accumulation | LOW | Standard floating-point best practice; no observed incident in this codebase specifically |

---

## Sources

- [Claude Code JSONL Logs Undercount Tokens by 100x](https://gille.ai/en/blog/claude-code-jsonl-logs-undercount-tokens/)
- [BUG: Output tokens incorrectly recorded in JSONL](https://github.com/anthropics/claude-code/issues/22686)
- [BUG: Duplicate entries in session .jsonl files](https://github.com/anthropics/claude-code/issues/5034)
- [BUG: Token Usage Statistics Duplicated in stream-json Mode](https://github.com/anthropics/claude-code/issues/6805)
- [Cache read tokens consume 99.93% of usage quota](https://github.com/anthropics/claude-code/issues/24147)
- [Rich: BUG Incorrect auto detection of terminal size on Windows #3412](https://github.com/Textualize/rich/issues/3412)
- [Rich: Texts isn't rendering correctly on Windows #135](https://github.com/Textualize/rich/issues/135)
- [Rich: Need better detection of terminal color capabilities #1640](https://github.com/Textualize/rich/issues/1640)
- [os.path.expanduser should not use HOME on Windows](https://github.com/python/cpython/issues/80445)
- [Snakemake: Cross-platform path handling str(Path) breaks shell commands on Windows](https://github.com/snakemake/snakemake/issues/3637)
- [Windows WinError 32 file sharing violation - Python Corner](https://medium.com/the-python-corner/python-how-to-open-a-file-on-windows-without-locking-it-24aea308a738)
- [setuptools Editable Installs PEP 660 documentation](https://setuptools.pypa.io/en/latest/userguide/development_mode.html)
- [pip install editable mode fails after pyproject.toml](https://github.com/pypa/setuptools/issues/3606)
- [Anthropic Pricing (official)](https://platform.claude.com/docs/en/about-claude/pricing)
- [Rich Console API documentation](https://rich.readthedocs.io/en/stable/console.html)
- [Enabling ANSI Colors in Windows CMD](https://sqlpey.com/c/enabling-ansi-colors-windows-cmd/)
- [Python pathlib Cookbook](https://miguendes.me/python-pathlib)
- [Claude-Code-Usage-Monitor upstream repository](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor)
- [Team Plan not supported issue #193](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor/issues/193)
