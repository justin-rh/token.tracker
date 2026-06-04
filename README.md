# Claude Token Tracker

Real-time Claude Code token usage dashboard for Windows. Monitors session token consumption, detects when you cross from included tokens into your overage pool, and shows burn rate projections — all from a system tray icon and terminal dashboard.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![Windows](https://img.shields.io/badge/platform-Windows-blue) ![License: MIT](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **INCLUDED / OVERAGE status** — instant visual indicator when you cross into the $500 overage pool
- **Pool burn rate** — $/hr derived from a rolling 30-minute sample window
- **Exhaustion projection** — estimated time until pool is depleted, with pre-reset warning
- **Per-project breakdown** — today and this-month token usage by project, sourced from local JSONL
- **Web sync** — authoritative utilization % and reset time pulled from claude.ai every 5 minutes
- **System tray icon** — color-coded coin (green → yellow → orange → red) that stays alive when the dashboard is hidden
- **Multi-plan support** — Pro, Max 5, Max 20, and custom token limits with P90 auto-calibration

---

## Requirements

- Windows 10 / 11
- Python 3.11+
- Claude Code installed and run at least once (populates `%APPDATA%\.claude\projects\`)

---

## Installation

```bash
git clone https://github.com/justin-rh/token.tracker.git
cd token.tracker
pip install -e .
```

---

## Usage

```bash
token-tracker
```

The dashboard auto-detaches to its own window, pins a coin icon to the system tray, and refreshes every 10 seconds. Settings from the last run are remembered — pass flags to override them.

### Common options

```bash
# Explicit plan
token-tracker --plan max20

# Custom token limit
token-tracker --plan custom --custom-limit-tokens 50000

# Table views
token-tracker --view daily
token-tracker --view monthly

# Appearance
token-tracker --theme dark --timezone America/New_York --time-format 12h

# Faster refresh
token-tracker --refresh-rate 5
```

### All CLI flags

| Flag | Options | Default | Description |
|------|---------|---------|-------------|
| `--plan` | `pro` `max5` `max20` `custom` | `custom` | Claude plan type |
| `--custom-limit-tokens` | integer | — | Token limit when `--plan custom` |
| `--view` | `realtime` `daily` `monthly` `session` | `realtime` | Display mode |
| `--theme` | `light` `dark` `classic` `auto` | `auto` | Color theme (auto-detects terminal background) |
| `--timezone` | IANA tz string or `auto` | `auto` | Display timezone |
| `--time-format` | `12h` `24h` `auto` | `auto` | Time format |
| `--refresh-rate` | 1–60 | `10` | Seconds between data refreshes |
| `--refresh-per-second` | 0.1–20 | `0.75` | Terminal render rate (Hz) |
| `--reset-hour` | 0–23 | — | Daily reset hour for session accounting |
| `--log-level` | `DEBUG` … `CRITICAL` | `INFO` | Log verbosity |
| `--log-file` | path | — | Write logs to file instead of stderr |
| `--debug` | flag | — | Shorthand for `--log-level DEBUG` |
| `--clear` | flag | — | Reset saved settings |
| `--version` | flag | — | Show version |

---

## System tray

The dashboard auto-hides to the system tray when you close the window. Right-click the coin icon for options:

| Action | Effect |
|--------|--------|
| Left-click | Toggle dashboard visibility |
| Open Dashboard | Restore window |
| Hide to Tray | Minimize to tray |
| Quit | Exit cleanly |

---

## Web sync setup

Pool utilization and reset time are fetched from claude.ai. On first launch you will be prompted to paste your `sessionKey` cookie:

1. Open [claude.ai](https://claude.ai) in your browser
2. Open DevTools → Application → Cookies → claude.ai
3. Copy the value of `sessionKey`
4. Paste it when prompted

The key is stored in Windows Credential Manager and reused on subsequent launches. Organization ID is discovered automatically.

---

## Data sources

| Data | Source |
|------|--------|
| Token counts | `%APPDATA%\.claude\projects\**\*.jsonl` (local, requestId-deduplicated) |
| Session cost | `~/.claude/statusline.jsonl → cost.total_cost_usd` |
| Utilization % / reset time | claude.ai usage API (web sync, every 5 min) |
| Auth credentials | Windows Credential Manager via `keyring` |
| Settings / pool state | `~/.claude-monitor/` |

> All cost figures displayed are **estimates** (local approximations). They are not authoritative billing data.

---

## How it works

Token Tracker reads Claude Code's local JSONL session files, deduplicates streaming entries by `requestId` (without this, counts inflate 100–174×), and groups entries into 5-hour session blocks. It infers your included-token limit using the P90 of historical sessions (requires ≥ 10 sessions before overage detection activates), then computes pool spend as the difference between total cost and the estimated included allowance.

---

## Development

```bash
# Run tests
pytest

# Lint
ruff check .
```

### Project layout

```
cli/            Entry point and bootstrap
core/           Plans, pricing, threshold, pool state, settings
data/           JSONL reader, session analyzer, aggregator
monitoring/     Orchestrator, data manager, web poller
terminal/       Manager, themes
ui/             Display controller, session display, tray manager
utils/          Formatting, timezone, notifications
```

---

## License

MIT
