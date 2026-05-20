# Claude Token Tracker

## Current Milestone: v2.1 Polish + Analytics

**Goal:** Fix the system tray window lifecycle, surface historical spend data, and clean up accuracy/quality issues carried forward from v2.0.

**Target features:**
- Minimize to tray — window hides on close, app stays alive; double-click restores
- Historical daily pool spend chart in the terminal dashboard
- Pool burn rate accuracy — derive $/hr from pool_spend_usd delta over a rolling time window
- Code quality fixes: WR-01 (test date skew), WR-02 (display-name collision logging), WR-03 (UTC billing-cycle consistency), WR-04 (f-string padding)

## What This Is

A Windows-compatible terminal dashboard and system tray indicator for Claude Code token usage, forked and adapted from [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor). v1.0 added Windows support and an overage pool layer. v2.0 switched to authoritative usage data from claude.ai, added a persistent color-coded system tray icon, and surfaced per-project token breakdowns. v2.1 focuses on tray window lifecycle, analytics, and polish.

## Core Value

Know instantly whether you're on included tokens or burning the $500 overage pool — and how fast.

## Requirements

### Validated

- ✓ Reads Claude Code session logs from Windows APPDATA path — v1.0 (Phase 1)
- ✓ requestId deduplication prevents 100–174x token inflation — v1.0 (Phase 1)
- ✓ Cost figures sourced from statusline.jsonl cost.total_cost_usd — v1.0 (Phase 1)
- ✓ Full-width Rich dashboard in Windows Terminal, VTP + UTF-8 safe — v1.0 (Phase 1)
- ✓ P90 threshold inference with 10-session cold-start guard — v1.0 (Phase 2)
- ✓ Calibrating / auto / manual threshold modes in dashboard — v1.0 (Phase 2)
- ✓ Prominent INCLUDED / OVERAGE status indicator — v1.0 (Phase 3)
- ✓ Est. pool spend, progress bar (green→yellow→red), burn rate, exhaustion projection — v1.0 (Phase 3)
- ✓ Pool spend persists via atomic pool_spend.json across restarts — v1.0 (Phase 3)
- ✓ Pool size and billing cycle start day configurable in config — v1.0 (Phase 3)
- ✓ All cost figures carry "est." prefix — v1.0 (Phase 3)
- ✓ Authoritative 5-hour utilization % and reset time from claude.ai, labeled "via claude.ai" — v2.0 (Phase 4)
- ✓ WebPoller daemon thread (5-min interval), "Last web sync: HH:MM:SS" in dashboard — v2.0 (Phase 4)
- ✓ Firefox/Chrome/keyring auth chain; manual sessionKey fallback to Credential Manager — v2.0 (Phase 4)
- ✓ Graceful fallback to "(est. — web unavailable)" on any fetch failure — v2.0 (Phase 4)
- ✓ Billing cycle reset detection with INFO log in pool_state_manager.py — v2.0 (Phase 4)
- ✓ Color-coded system tray icon (green/yellow/red) via pystray + Pillow — v2.0 (Phase 5)
- ✓ Tray tooltip, right-click menu (Open Dashboard / Quit), left-click window toggle — v2.0 (Phase 5)
- ✓ Clean tray shutdown via CTRL_C_EVENT — no ghost icons — v2.0 (Phase 5)
- ✓ Per-project token breakdown — Today (est.) / This month (est.) side-by-side columns — v2.0 (Phase 6)
- ✓ Per-project data exclusively from JSONL, never merged with web data — v2.0 (Phase 6)
- ✓ Billing cycle start uses UTC (`datetime.now(timezone.utc).date()`), not local `date.today()` — v2.1 (Phase 7)
- ✓ Display-name collision logged at WARNING with both slugs identified — v2.1 (Phase 7)
- ✓ Per-project row columns align correctly via `_col_pad()` for Rich markup + emoji — v2.1 (Phase 7)
- ✓ Test suite is deterministic — billing period tests use injected fixed dates, no `date.today()` — v2.1 (Phase 7)

### Active

- Minimize to tray — window hides on close, app stays alive; double-click restores
- Historical daily pool spend chart in terminal dashboard
- Pool burn rate derived from pool_spend_usd delta over rolling time window

### Out of Scope

- Linux/Mac support — Windows-first; cross-platform adds complexity without benefit for this user
- Web UI or browser-based dashboard — terminal dashboard + system tray covers the need
- Email/Slack/push notifications — visual dashboard is the interaction model
- Multi-user / team aggregation — single-user local tool; requires backend infrastructure
- Overage pool balance from web API — claude.ai usage endpoint returns utilization % only; JSONL accumulation remains the source
- Historical monthly spend chart — deferred to v2.1 analytics milestone
- Terminal bell at configurable pool % threshold — deferred to v2.1

## Context

- **Reference tool**: [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) — Python package (v3.1.0), uses Rich for terminal UI, reads `~/.claude/projects/` JSONL files, calculates P90 percentile limits, supports Pro/Max5/Max20 plans
- **Platform**: Windows 11 Enterprise — the reference tool has Unix path assumptions adapted for `C:\Users\...`
- **Company plan**: Justin is on a company Anthropic plan with an included daily token allocation and a $500 overage pool that silently activates when included tokens are exhausted
- **Primary pain**: No visibility into when usage crosses from included → overage; the $500 pool depletes silently
- **Tech stack**: Python, Rich terminal UI, pystray, Pillow, keyring, browser-cookie3, httpx. ~8,731 Python source LOC (excl. tests). Threading model: main thread (Rich Live), MonitoringThread (JSONL, 10s), WebPollerThread (claude.ai HTTP, 300s Event.wait), Tray (pystray run_detached from main thread).
- **v2.0 key finding**: Cloudflare NOT blocking urllib.request or httpx on claude.ai — no curl_cffi needed. Corporate SSL inspection requires verify=False on httpx calls (matches existing urllib.request behavior).

## Constraints

- **Platform**: Windows 11 — paths, terminal rendering, and file handling must work on Windows
- **Data source**: `~/.claude/projects/` JSONL logs for per-project breakdown; claude.ai web API for authoritative totals
- **Threshold**: Daily included-token limit is unknown — inferred via P90 or replaced by web utilization when available
- **Pool size**: $500 overage pool — user-configurable in config.json

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork the reference tool | Avoids rebuilding JSONL reader, P90 calc, Rich UI from scratch | ✓ Validated v1.0 |
| P90 threshold detection | User doesn't know exact daily limit; P90 of historical sessions is proven approach | ✓ Validated v1.0 |
| $500 pool size is configurable | Pool size could change; hardcoding requires code change | ✓ Validated v1.0 |
| Windows-first scope | User is on Windows; cross-platform adds complexity without benefit | ✓ Validated v1.0 |
| pool_state_manager mirrors ThresholdManager pattern | Consistent frozen dataclass + factory fn; same test fixtures | ✓ Validated v1.0 |
| Burn rate uses current session rate (not historical) | Simpler to compute; labeled as "est." to set expectations | ✓ Validated v1.0 |
| Firefox-first cookie extraction | Chrome/Edge ABE (v127+) may block browser-cookie3; Firefox is guaranteed path | ✓ Validated v2.0 |
| WebPoller as daemon thread with Event.wait(300) | Clean stop signal; daemon=True guarantees thread death even if finally skipped | ✓ Validated v2.0 |
| TrayManager uses run_detached() from main thread | Avoids separate OS thread for pystray; race-free with setup callback | ✓ Validated v2.0 |
| SSL verify=False on httpx calls | Corporate proxy performs SSL inspection; matches existing urllib.request behavior | ✓ Validated v2.0 |
| _col_pad() for Rich markup-aware padding | f-string :<N counts Python chars, not terminal columns; breaks on markup + emoji | ✓ Validated v2.0 |
| Per-project data exclusively from JSONL | Web API returns only aggregate totals; per-project attribution is JSONL-only | ✓ Validated v2.0 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-20 — Phase 7 complete — code quality fixes validated*
