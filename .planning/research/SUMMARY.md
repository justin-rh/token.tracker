# Research Summary: Claude Token Tracker v2.0

**Synthesized from:** STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md
**Date:** 2026-05-18

## Executive Summary

v2.0 is an extension milestone, not a rebuild. `core/usage_fetcher.py` already exists with Chrome DPAPI, Edge support, and HTTP fetches to the claude.ai API — the "cookie extractor" and "web fetcher" are extensions of this module. Two net-new modules (`monitoring/web_poller.py`, `ui/tray_manager.py`) and one new dataclass (`WebUsageData`) cover the entire new surface area.

The highest-uncertainty question: **can Python reliably fetch data from claude.ai?** Two blockers exist:
1. Chrome App-Bound Encryption (v127+, July 2024) — breaks browser-cookie3 on Chrome AND Edge. Firefox is unaffected. Firefox-first.
2. Cloudflare bot detection — confirmed to block headless Python in anthropics/claude-code#39896. Mitigation: `curl_cffi` with browser TLS impersonation. Must be tested on the actual machine first.

A manual sessionKey paste fallback is not optional — it is the guaranteed ship path if both mitigations fail.

## Stack Additions

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `browser-cookie3` | >=0.20.1 | Extract sessionKey from Firefox/Chrome | Firefox-first; Chrome v127+ blocked by ABE |
| `httpx` | >=0.27.0 | HTTP client for claude.ai API | Native CookieJar support; replace requests |
| `Pillow` | >=10.0.0 | System tray icon generation | Runtime PIL.Image, no external file needed |
| `pywin32` | >=306 | Windows DPAPI (transitive dep) | Already present via usage_fetcher.py |
| `pystray` | >=0.19.5 | System tray icon on Windows | Use run_detached(), NOT run() or daemon thread |
| `curl_cffi` | evaluate at Phase 4 | Cloudflare bypass (if httpx blocked) | Do not pre-add; test first |
| `pytest-httpx` | >=0.30.0 (dev) | Mock httpx in tests | Replaces live network calls in CI |

## Feature Table Stakes

| Feature | Expected Behavior |
|---------|-------------------|
| Cookie auth (auto + manual) | Firefox → Chrome → manual sessionKey paste; never store in plaintext config |
| Web utilization % in dashboard | Authoritative % replaces P90 inference; all web values labeled "via claude.ai" |
| JSONL-only graceful fallback | Web fetch failure → "(est. — web data unavailable)"; no crash, no blank display |
| System tray icon | Persistent in notification area; green <50%, yellow 50–75%, red >75%; tooltip shows % |
| Tray right-click menu | "Open Dashboard" + "Quit" minimum; Quit triggers clean shutdown |
| 5-minute auto-refresh | WebPoller thread re-fetches every 5 min; UI shows "last updated HH:MM:SS" |
| Monthly pool spend reset | Resets on configurable billing cycle start day; UTC internally; logs reset event |
| Source labeling | Web-derived = "via claude.ai"; JSONL-derived = "est."; sources never silently mixed |

## Architecture Changes

**Extended (not rebuilt):**
- `core/usage_fetcher.py` — add `fetch_web_usage() -> Optional[WebUsageData]`
- `core/pool_state_manager.py` — accept optional `web_usage` param; web values win when present
- `monitoring/orchestrator.py` — add `set_web_poller()`, add `web_usage` key to `monitoring_data`
- `ui/session_display.py` — add web-sourced display rows via `web_usage` kwarg
- `cli/main.py` — wire WebPoller + TrayManager; stop both in existing `finally` block

**New modules:**
- `core/models.py` — add `WebUsageData` frozen dataclass
- `monitoring/web_poller.py` — daemon thread + threading.Event stop + threading.Lock cache
- `ui/tray_manager.py` — pystray wrapper using `run_detached()`; Pillow color circle

**Threading model:**

| Thread | Role | Interval |
|--------|------|----------|
| Main | Rich Live display | 1s sleep loop |
| MonitoringThread | JSONL read + callbacks | existing (10s) |
| WebPollerThread | claude.ai HTTP fetch | 300s (Event.wait) |

Tray: `icon.run_detached()` from main thread before Rich Live loop — not a 4th thread.

## Critical Risks

1. **Cloudflare blocks httpx (Phase 4, day 1)** — Test first. If blocked, switch to `curl_cffi`. If still blocked on corporate network, ship JSONL-only.

2. **Chrome/Edge ABE breaks cookie extraction (Phase 4)** — Firefox-first extraction order. Manual paste as fallback. Never assume browser-cookie3 will work without testing.

3. **claude.ai API schema can change without notice (ongoing)** — Use `.get("key", default)` everywhere. Log raw response at DEBUG. Surface schema-change warning when expected keys absent.

4. **pystray run() blocks main thread — must use run_detached() (Phase 5)** — Daemon thread teardown causes ghost icons. `icon.run_detached()` then Rich loop is the only clean pattern.

5. **Monitoring thread dying silently (Phase 4/5)** — New web fetch paths add new failure modes. Outer `except Exception` must cover them. Add watchdog check in `cli/main.py`.

## Recommended Phase Order

- **Phase 4: Web Data Foundation** — Spike (Cloudflare + cookie test) first, then WebUsageData, fetch_web_usage, WebPoller, orchestrator wiring, terminal dashboard rows
- **Phase 5: System Tray** — TrayManager with run_detached(), cli wiring, clean shutdown
- **Phase 6: Hybrid Display (conditional)** — Only extract data/web_merger.py if Phase 4 display additions exceed ~30 lines in session_display.py
- **Phase 7: Monthly Reset Hardening** — Validate UTC, billing_start_day edge cases, reset logging
