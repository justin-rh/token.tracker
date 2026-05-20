---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Polish + Analytics
status: roadmap
stopped_at: ~
last_updated: "2026-05-20T00:00:00.000Z"
last_activity: 2026-05-20 — Roadmap created for v2.1 (Phases 7–10)
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-20)

**Core value:** Know instantly whether you're on included tokens or burning the $500 overage pool — and how fast.
**Current focus:** v2.1 roadmap defined — ready for phase planning via /gsd-plan-phase 7

## Current Position

Phase: 7 (not started — roadmap complete, planning next)
Plan: —
Status: Roadmap created; ready for /gsd-plan-phase 7
Last activity: 2026-05-20 — v2.1 roadmap written (Phases 7–10, 13 requirements mapped)

## Progress Bar

```
v2.1: [                                        ] 0% (0/TBD plans complete, 0/4 phases complete)
```

## Accumulated Context

### Decisions

- v1.0 decisions logged in PROJECT.md Key Decisions table
- v2.0: Switch data source from JSONL-only to hybrid (claude.ai web API for totals + JSONL for per-project breakdown)
- v2.0: P90 threshold inference replaced by actual plan limits from claude.ai when web data is available
- v2.0: pool_state_manager extended (not replaced) to accept optional web_usage param
- v2.0: System tray added via pystray + Pillow using run_detached() — never run() or daemon thread
- v2.0: Firefox-first cookie extraction; Chrome/Edge ABE (v127+) may block browser-cookie3; manual sessionKey paste is the guaranteed fallback
- v2.0: Phase 4 MUST spike Cloudflare + cookie extraction on the actual machine before writing any parsing code
- v2.0: curl_cffi is a conditional dep — add only if httpx is blocked by Cloudflare; do not pre-add
- v2.0 04-01: plan_limit_tokens is Optional[int] — None for Teams/Enterprise where API returns monthly_limit in cents (not tokens)
- v2.0 04-02: _read_auth_cookies() follows keyring(1) > Firefox(2) > Chrome(3) — D-06 implemented; session_key value never logged
- v2.0 04-02: five_hour.utilization assumed 0-100 scale (same as extra_usage; ASSUMED comment added); only seen 0.0 in spike
- v2.0 04-02: Teams reset_at derived from billing_cycle_start_day config (no API resets_at for Teams extra_usage branch)
- v2.0 04-03: WebPoller subclasses threading.Thread directly (daemon=True); Event.wait(300) loop idiom; no join() in stop(); org_id never logged
- v2.0 04-04: Optional[Any] used for _web_poller type annotation in orchestrator (avoids circular import); web_usage follows pool_state pattern exactly
- v2.0 04-05: dt_timezone alias used for datetime.timezone (avoids shadowing by 'timezone: str' positional param); _show_threshold_rows guard suppresses Phase 2 block when web_usage present (Pitfall 7)
- v2.0 05-01: TrayManager uses run_detached() + setup callback for race-free visible=True; CTRL_C_EVENT not SIGINT; OSError fallback in _quit()
- v2.0 05-02: TrayManager started unconditionally (no org_id guard) — shows -- until first WebPoller result; PowerShell-in-shell window-toggle limitation is known v2.0 scope item
- v2.1: Phase 7 (QUAL) before Phase 8 (BURN) — quality fixes are isolated and establish a clean baseline before touching the monitoring orchestrator
- v2.1: Phase 9 (TRAY) parallel-eligible with Phase 8 but sequenced after to keep plan scope tight; both depend only on Phase 7
- v2.1: Phase 10 (ANLX) depends on Phase 8 — chart data source is pool_state_manager billing-period block iteration; burn rate ring buffer work in Phase 8 may touch same module

### Architecture Notes

**Extended modules (not rebuilt):**

- `core/usage_fetcher.py` — add `fetch_web_usage() -> Optional[WebUsageData]`
- `core/pool_state_manager.py` — accept optional `web_usage` param; web values win when present
- `monitoring/orchestrator.py` — add `set_web_poller()`, add `web_usage` key to `monitoring_data`
- `ui/session_display.py` — add web-sourced display rows via `web_usage` kwarg
- `cli/main.py` — WebPoller + TrayManager wired; both stopped in existing `finally` block (DONE)

**New modules (DONE):**

- `core/models.py` — `WebUsageData` frozen dataclass (DONE 04-01)
- `monitoring/web_poller.py` — daemon thread + threading.Event stop + threading.Lock cache (300s interval) (DONE 04-03)
- `ui/tray_manager.py` — pystray wrapper using `run_detached()`; Pillow color circle (DONE 05-01)

**Threading model:**

- Main thread: Rich Live display (1s sleep loop)
- MonitoringThread: JSONL read + callbacks (existing, 10s)
- WebPollerThread: claude.ai HTTP fetch (300s Event.wait)
- Tray: `icon.run_detached()` from main thread — not a 4th thread

**v2.1 implementation notes:**

- TRAY (Phase 9): use `ctypes.windll.user32.ShowWindow` / `GetConsoleWindow()` for hide/restore; constraint — GetConsoleWindow() returns outer shell HWND when launched inside a shell; fix applies cleanly only for standalone launch
- BURN (Phase 8): add `collections.deque` ring buffer of `(timestamp, pool_spend_usd)` tuples in monitoring orchestrator; burn rate = delta_spend / delta_time across buffer; hide row when len(buffer) < 2
- ANLX (Phase 10): chart renders inside Rich panel using block characters or Rich Bar; data source is existing billing-period block iteration in pool_state_manager
- QUAL (Phase 7): four isolated single-file edits — test fixtures (WR-01), logging call (WR-02), datetime normalization (WR-03), _col_pad() usage (WR-04)

### Pending Todos

- (none — v2.0 milestone complete; v2.1 roadmap ready)

### Blockers/Concerns

- Chrome App-Bound Encryption (v127+) may block browser-cookie3 on Chrome/Edge — Firefox-first, manual fallback mandatory
- claude.ai API schema has no stability guarantee — use `.get("key", default)` everywhere; log raw response at DEBUG
- **Teams/Enterprise accounts**: `five_hour` field is null; use `extra_usage.utilization` instead. `extra_usage` monetary fields are in cents (not tokens). Both branches handled in 04-02 plan.
- **session_key currently in plaintext config.json** — 04-06 plan migrates it to keyring on first run (D-04)
- TRAY Phase 9: GetConsoleWindow() HWND constraint when launched inside a shell is a known limitation; fix scope is standalone launch only

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Alerts | ALRT-01: Terminal bell at configurable pool % threshold | v2.2+ | v2.0 scope definition |
| Analytics | Historical monthly spend beyond current billing cycle | v2.2+ | v2.1 scope definition |

Items acknowledged and deferred at milestone close on 2026-05-19:

| Category | Item | Status |
|----------|------|--------|
| uat_gap | Phase 05 — 05-HUMAN-UAT.md | partial |
| verification_gap | Phase 05 — 05-VERIFICATION.md | human_needed |
| verification_gap | Phase 06 — 06-VERIFICATION.md | human_needed |

## Session Continuity

Last session: 2026-05-20
Stopped at: roadmap creation complete
Resume file: None
