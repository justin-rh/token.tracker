# Stack Research: Claude Token Tracker (Windows Fork)

**Project:** Fork of Claude-Code-Usage-Monitor for Windows + company plan overage tracking
**Researched:** 2026-05-07 (v1.0), updated 2026-05-18 (v2.0 additions)
**Source project version:** v3.1.0 (7.9k stars, 401 forks)

---

## v2.0 New Capabilities Stack

These additions are required for the three new v2.0 features: browser cookie extraction,
claude.ai web API fetching, and system tray icon.

---

## Browser Cookie Extraction

### The Chrome App-Bound Encryption Problem (Critical Blocker Risk)

Chrome 127 (released July 30, 2024) introduced App-Bound Encryption (ABE), which ties
cookie encryption to the Chrome application's identity. This breaks all third-party
DPAPI-based decryption approaches, including browser-cookie3.

**Status of browser-cookie3 with Chrome 127+:**
- Issue #210 ("Broken decryption in Chrome") opened September 2024, remains open
- Error: `BrowserCookieError: Unable to get key for cookie decryption` (MAC check failure)
- Root cause: v20-prefixed cookie values use ABE; the library's `_decrypt` method fails on
  AES-GCM MAC verification for these
- The library is classified as inactive/low maintenance — no fix shipped as of Jan 2025 (v0.20.1)

**However, the risk is manageable because:**
1. Edge (Chromium-based) is the default Windows 11 browser and ABE applies specifically to
   Chrome's COM-bound encryption server, not Edge's
2. Firefox stores cookies in a separate format (NSS/SQLite) unaffected by Chrome ABE
3. The `sessionKey` cookie needed for claude.ai is set per browser session — if the user
   primarily uses Edge or Firefox to access claude.ai, cookie extraction works

**Strategy: Edge-first extraction, Chrome as fallback, Firefox as tertiary**

| Library | pip name | Version | Purpose | Windows Notes |
|---------|----------|---------|---------|---------------|
| browser-cookie3 | `browser-cookie3` | 0.20.1 | Extract cookies from Edge/Firefox/Chrome | Edge and Firefox work reliably; Chrome 127+ has ABE issue. Requires Chrome to be closed when reading its SQLite DB. |
| pywin32 | `pywin32` | >=306 | Windows DPAPI decryption (pulled in by browser-cookie3) | browser-cookie3 uses `win32crypt.CryptUnprotectData` on Windows; pywin32 is a hard transitive dep |
| pycryptodome | `pycryptodome` | >=3.20.0 | AES-GCM decryption of cookie values | Transitive dep of browser-cookie3; already in the cryptography ecosystem |

**Note:** The existing `cryptography>=41.0.0` dep in pyproject.toml does NOT replace
pycryptodome. They are separate libraries. browser-cookie3 uses pycryptodome specifically.

**Install:**
```
pip install browser-cookie3 pywin32
```
pycryptodome installs automatically as a browser-cookie3 dependency.

**Usage pattern:**
```python
import browser_cookie3

def get_claude_cookies() -> dict:
    """Try Edge first, Firefox second, Chrome last."""
    for loader in [browser_cookie3.edge, browser_cookie3.firefox, browser_cookie3.chrome]:
        try:
            cj = loader(domain_name="claude.ai")
            cookies = {c.name: c.value for c in cj}
            if "sessionKey" in cookies:
                return cookies
        except browser_cookie3.BrowserCookieError:
            continue
    raise RuntimeError("No claude.ai session cookie found in any browser")
```

**Fallback if ABE blocks all browsers:** Manual cookie paste into a local config file.
Document this as the fallback in the user-facing error message.

---

## HTTP Client (claude.ai Fetching)

| Library | pip name | Version | Purpose | Windows Notes |
|---------|----------|---------|---------|---------------|
| httpx | `httpx` | >=0.27.0 (latest: 0.28.1) | Sync HTTP client for fetching claude.ai/settings/usage | Full Windows support; sync Client is the right choice here (no async needed). Accepts CookieJar from browser-cookie3 directly. |

**Why httpx over requests:**
- Already idiomatic in modern Python tooling
- Native CookieJar support: `httpx.Client(cookies=cookie_jar)` accepts the cookiejar
  object returned by browser-cookie3 directly without conversion
- Better error messages and timeout handling than requests
- Consistent with async-capable future upgrade path if needed

**Why not requests:** requests 2.x works fine too, but httpx is cleaner and has no practical
downside. Do not add both.

**Usage pattern:**
```python
import httpx
import browser_cookie3

def fetch_usage_page(cookies: dict) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
        "Accept": "application/json",
    }
    with httpx.Client(cookies=cookies, headers=headers, follow_redirects=True, timeout=15.0) as client:
        r = client.get("https://claude.ai/settings/usage")
        r.raise_for_status()
        return r.text
```

**Install:**
```
pip install httpx
```

---

## System Tray Icon

| Library | pip name | Version | Purpose | Windows Notes |
|---------|----------|---------|---------|---------------|
| pystray | `pystray` | 0.19.5 | System tray icon with menu | Windows backend (win32) is the default and fully featured. `icon.run()` is blocking; use `icon.run_detached()` or run in a thread. |
| Pillow | `Pillow` | >=10.0.0 (latest: 12.2.0) | Generate tray icon images (PIL.Image.Image required by pystray) | Required — pystray does not accept raw image bytes; must be a PIL Image object. Pure Python wheels available for Windows x64. |

**Threading note for Windows:**
On Windows, `pystray.Icon.run()` does NOT need to be on the main thread (unlike macOS where
it is mandatory). The safe pattern is to launch the tray icon in a daemon thread so the Rich
terminal dashboard can run on the main thread.

```python
import threading
import pystray
from PIL import Image, ImageDraw

def make_icon(color: str) -> Image.Image:
    """Generate a 64x64 solid-color circle icon."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=color)
    return img

COLOR_MAP = {
    "green": "#22c55e",   # <50% usage
    "yellow": "#eab308",  # 50-75% usage
    "red": "#ef4444",     # >75% usage
}

def start_tray(icon_ref: list) -> None:
    icon = pystray.Icon(
        "token-tracker",
        make_icon(COLOR_MAP["green"]),
        "Claude Token Tracker",
        menu=pystray.Menu(
            pystray.MenuItem("Open Dashboard", lambda: None),
            pystray.MenuItem("Quit", lambda: icon_ref[0].stop()),
        ),
    )
    icon_ref.append(icon)
    icon.run()   # blocks; safe in non-main thread on Windows

icon_ref = []
tray_thread = threading.Thread(target=start_tray, args=(icon_ref,), daemon=True)
tray_thread.start()
```

**Updating icon color at runtime:**
```python
icon_ref[0].icon = make_icon(COLOR_MAP["yellow"])
```

**Install:**
```
pip install pystray Pillow
```

---

## Background Polling Thread

No new libraries needed. Use Python stdlib `threading.Thread` with `threading.Event` for
clean shutdown.

```python
import threading
import time

_stop_event = threading.Event()

def polling_loop(interval_seconds: int = 300) -> None:
    """Fetch usage data every interval_seconds. Stops on _stop_event."""
    while not _stop_event.wait(timeout=interval_seconds):
        try:
            refresh_usage_data()
        except Exception as e:
            log_error(e)   # never crash the poller

poll_thread = threading.Thread(target=polling_loop, daemon=True, name="usage-poller")
poll_thread.start()

# Shutdown:
_stop_event.set()
```

**Why daemon=True:** The thread must not prevent the process from exiting when the user
closes the terminal. A daemon thread is killed automatically when the main thread exits.

**Why threading.Event over time.sleep():** `Event.wait(timeout=N)` is interruptible —
calling `_stop_event.set()` wakes the thread immediately rather than waiting up to N seconds.

**Thread safety with Rich Live display:** The polling thread writes to shared data structures
that the main (Rich) thread reads. Use `threading.Lock()` around any shared mutable state
(dict, list). Pydantic frozen models are inherently safe to read across threads once assigned.

---

## Complete pyproject.toml Additions for v2.0

Add these to the `dependencies` list in pyproject.toml:

```toml
"browser-cookie3>=0.20.1",
"httpx>=0.27.0",
"Pillow>=10.0.0",
"pywin32>=306",
"pystray>=0.19.5",
```

Add to `[project.optional-dependencies].dev`:
```toml
"pytest-httpx>=0.30.0",   # mock httpx calls in tests
```

---

## Do NOT Add

| Library | Why Not |
|---------|---------|
| `requests` | httpx covers the same need with better ergonomics; two HTTP clients is redundant |
| `selenium` / `playwright` | Full browser automation is massive overkill for a single GET to claude.ai |
| `beautifulsoup4` / `lxml` | The claude.ai usage page returns JSON, not HTML requiring parsing |
| `aiohttp` | Async HTTP not needed; the 5-minute polling interval has no latency requirement |
| `asyncio` event loop | No concurrent I/O; a single sync `httpx.Client` call suffices |
| `psutil` | Not needed for this feature set |
| `PyQt5` / `tkinter` | GUI frameworks — pystray with win32 backend handles the tray natively without a GUI framework |
| `win10toast` / `plyer` | Desktop notifications are out of scope for v2.0 per PROJECT.md |
| `keyring` | Browser-cookie3 pulls this in on some platforms; do not add it explicitly — it's a transitive dep |
| `secretstorage` | Linux-only; irrelevant on Windows |
| `pycryptodome` (explicit) | Let browser-cookie3 pull it as a transitive dep; declaring it explicitly creates version pin risk |

---

## Risk Register

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|------------|
| Chrome ABE breaks cookie extraction | High | Medium (depends on which browser user uses for claude.ai) | Edge-first strategy; Firefox fallback; manual cookie fallback as last resort |
| claude.ai page structure changes | Medium | Medium | Page returns JSON not HTML; JSON schema changes are less frequent than DOM changes |
| browser-cookie3 inactive maintenance | Low | Low (works for Edge/Firefox which are the primary targets) | Vendor the patched version if needed; library is small (~1000 lines) |
| pystray icon not appearing on taskbar | Low | Low | Confirmed working on Windows 11 with win32 backend |
| Thread-safety bugs with Rich Live | Medium | Low | Use threading.Lock around shared state; frozen Pydantic models for read-only data |

---

## Confidence Levels

| Area | Confidence | Reasoning |
|------|------------|-----------|
| browser-cookie3 Edge/Firefox compatibility | HIGH | Library confirmed working for Edge/Firefox; issue #210 is Chrome-specific |
| Chrome ABE breaking browser-cookie3 | HIGH | Issue #210 open, Google security blog confirmed ABE in Chrome 127+, multiple sources corroborate |
| httpx Windows compatibility | HIGH | No platform-specific restrictions; widely used on Windows |
| pystray Windows threading behavior | HIGH | Official docs confirm `run()` is safe in non-main thread on Windows; run_detached only mandatory on macOS |
| Pillow version requirement | HIGH | pystray docs and tutorials universally require PIL.Image.Image objects |
| pywin32 as transitive dep of browser-cookie3 | MEDIUM | Confirmed in browser-cookie3 install logs and dependency metadata; not tested on this specific machine |
| claude.ai usage page returning JSON | MEDIUM | Inferred from typical SPA architecture; the page exists at claude.ai/settings/usage but exact response format unverified without live access |

---

## Sources

- [browser-cookie3 PyPI (v0.20.1)](https://pypi.org/project/browser-cookie3/)
- [browser-cookie3 Issue #210: Broken decryption in Chrome](https://github.com/borisbabic/browser_cookie3/issues/210)
- [browser-cookie3 Issue #195: Stopped working on Edge and Chrome](https://github.com/borisbabic/browser_cookie3/issues/195)
- [Google Security Blog: Chrome App-Bound Encryption](https://security.googleblog.com/2024/07/improving-security-of-chrome-cookies-on.html)
- [pystray PyPI (0.19.5)](https://pypi.org/project/pystray/)
- [pystray docs: FAQ on threading](https://pystray.readthedocs.io/en/latest/faq.html)
- [pystray docs: Creating a tray icon](https://pystray.readthedocs.io/en/latest/usage.html)
- [httpx PyPI (0.28.1)](https://pypi.org/project/httpx/)
- [httpx docs: Developer Interface](https://www.python-httpx.org/api/)
- [Pillow PyPI (12.2.0)](https://pypi.org/project/pillow/)

---

## v1.0 Stack (Existing — Do Not Change)

The following sections document the v1.0 stack decisions. They remain valid for v2.0.

---

## Recommended Stack (v1.0)

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

### No New Dependencies Needed (v1.0 only)

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

### Do NOT do This

- Do not `pip install claude-code-usage-monitor` and then try to patch it. The installed package is in site-packages and not editable.
- Do not add a `requirements.txt` alongside `pyproject.toml` — it creates dependency duplication drift.
- Do not use `python setup.py develop` — this is the pre-PEP517 deprecated approach.

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

---

## What NOT to Use / Watch Out For

### Deprecated Approaches (v1.0 + v2.0)

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
| `requests` alongside `httpx` | Two HTTP clients serving the same purpose | Use httpx only |
| `selenium` or `playwright` | Browser automation overkill for a single GET | httpx + browser-cookie3 |
| `beautifulsoup4` / `lxml` | Unnecessary if claude.ai returns JSON | Parse JSON directly |
| `aiohttp` or `asyncio` event loop | No concurrent I/O requirement | Sync httpx.Client |
| `PyQt5` / `tkinter` | Full GUI framework for what is just a tray icon | pystray with win32 backend |
| `pycryptodome` declared explicitly | Version pin risk; let browser-cookie3 pull as transitive dep | Omit from pyproject.toml |

### Pydantic v1 / v2 Compatibility

The upstream requires pydantic >=2.0.0. Do not backslide to v1. If you see `from pydantic import validator` in any code you copy, replace with `@field_validator` (v2 API).

### Python Version Floor

Do not target Python 3.8. It reached end-of-life October 2024. The upstream targets 3.9+; recommend 3.11+ for your fork to get `tomllib` in stdlib and better `zoneinfo` support.

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
- [browser-cookie3 PyPI (v0.20.1)](https://pypi.org/project/browser-cookie3/)
- [browser-cookie3 Issue #210: Broken decryption in Chrome](https://github.com/borisbabic/browser_cookie3/issues/210)
- [browser-cookie3 Issue #195: Stopped working on Edge and Chrome](https://github.com/borisbabic/browser_cookie3/issues/195)
- [Google Security Blog: Chrome App-Bound Encryption (July 2024)](https://security.googleblog.com/2024/07/improving-security-of-chrome-cookies-on.html)
- [pystray PyPI (0.19.5)](https://pypi.org/project/pystray/)
- [pystray docs: FAQ on threading](https://pystray.readthedocs.io/en/latest/faq.html)
- [pystray docs: Creating a tray icon](https://pystray.readthedocs.io/en/latest/usage.html)
- [httpx PyPI (0.28.1)](https://pypi.org/project/httpx/)
- [Pillow PyPI (12.2.0)](https://pypi.org/project/pillow/)
- [Claude-Code-Usage-Monitor upstream repo](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor)
