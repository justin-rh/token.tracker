# Phase 1: Windows Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 01-windows-foundation
**Areas discussed:** Code layout, Windows path resolution, Active session file handling, statusline.jsonl cost source

---

## Code Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Repo root | Copy package files directly to root — run as `python monitor.py`. Simplest. | ✓ |
| src/ subfolder | Code in src/monitor/ — cleaner packaging, extra directory depth | |
| Keep original package name | Clone into claude_code_usage_monitor/ — easiest to diff upstream | |

**User's choice:** Repo root — `python monitor.py` entry point
**Notes:** No install step required; run from repo root.

---

## Windows Path Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| os.environ[APPDATA] | `Path(os.environ['APPDATA']) / '.claude' / 'projects'` — explicit, always correct on Windows 11 | ✓ |
| Constructed from home | `Path.home() / 'AppData' / 'Roaming' / '.claude' / 'projects'` — fragile with roaming profiles | |
| Env var override first | Check CLAUDE_CONFIG_DIR, fall back to APPDATA — flexible but more config surface | |

**User's choice:** `os.environ["APPDATA"]` approach
**Notes:** CLAUDE.md documents this as the canonical approach for this project.

---

## Active Session File Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Skip with (active) indicator | Show note in dashboard when active session is unreadable | ✓ |
| Skip silently | Omit locked file with no explanation | |
| Force-read with win32 flags | ctypes/win32api FILE_SHARE_READ — reads locked file, adds platform dependency | |

**User's choice:** Skip with "(active session — data not yet visible)" indicator
**Notes:** Silent skip rejected because user needs to know current session data is excluded.

---

## statusline.jsonl Cost Source

| Option | Description | Selected |
|--------|-------------|----------|
| statusline.jsonl primary, pricing fallback | Best real-world accuracy with graceful degradation | ✓ |
| statusline.jsonl only | Purist but breaks for sessions without statusline entry | |
| Pricing engine only | Skip PORT-03 for now — rejected due to costUSD field removal at v1.0.9 | |

**User's choice:** statusline.jsonl primary with pricing engine fallback

| Structure option | Description | Selected |
|-----------------|-------------|----------|
| One entry per session | Match by session ID or timestamp | ✓ |
| Running total only | Delta-based inference | |
| Claude decides | Inspect actual file first | |

**User's choice:** Assume one entry per session; adapt if the actual file differs.

---

## Claude's Discretion

- requestId deduplication timing (read-time vs post-parse) — implementation detail
- Rich Console width wiring location — implementation detail
- Exact wording/placement of active session indicator — implementation detail

## Deferred Ideas

- CLAUDE_CONFIG_DIR env var override — deferred, add if needed in future phase
- MAX_PATH handling — deferred, surface when real data triggers it
- Cross-platform path stubs — out of scope for v1
