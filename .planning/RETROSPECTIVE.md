# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.0 — Windows Foundation + Overage Pool

**Shipped:** 2026-05-08
**Phases:** 3 | **Plans:** 11

### What Was Built
- Forked Claude-Code-Usage-Monitor and ported to Windows — APPDATA path, requestId dedup, statusline.jsonl cost source
- P90 threshold detection with 10-session cold-start guard; auto/manual/calibrating modes end-to-end
- Overage pool dashboard: INCLUDED/OVERAGE status, est. pool spend, progress bar, burn rate, pool_spend.json persistence

### What Worked
- Forking reference tool gave a working foundation — Rich UI, JSONL reader, P90 calc all reused without change
- ThresholdManager frozen dataclass + factory fn pattern set a template reused throughout v2.0
- Phase 3 executed in <1 min per plan — architecture was well-specified before execution

### What Was Inefficient
- Python 3.12 shim breakage discovered late in Phase 1 (01-05) — could have been caught in 01-01 with a version compatibility check

### Patterns Established
- Frozen dataclass + factory fn (ThresholdManager, PoolState) as the standard data model pattern
- kwargs.get() in session_display for optional display params — avoids signature explosion on a 21-param function
- All dollar values carry inline "est." prefix — established as a non-negotiable UI rule

### Key Lessons
1. Spike unknown platform behavior first (VTP, UTF-8) before building display layer on top
2. requestId deduplication is essential — without it, streaming entries inflate counts 100–174x

---

## Milestone: v2.0 — Web-Sourced Usage + System Tray

**Shipped:** 2026-05-19
**Phases:** 6 total (4–6 added in v2.0) | **Plans:** 23 total (12 added in v2.0)
**Timeline:** 2026-05-07 → 2026-05-19 (12 days end-to-end across both milestones)

### What Was Built
- claude.ai web integration — Firefox/Chrome cookie extraction, keyring storage, WebPoller daemon thread (5-min interval), authoritative 5-hour utilization % and reset time in terminal dashboard
- Full data pipeline: WebPoller → monitoring_data → display_controller → session_display, with graceful "(est. — web unavailable)" fallback
- Color-coded system tray icon (green/yellow/red) via pystray + Pillow — tooltip, right-click menu, left-click window toggle, clean shutdown via CTRL_C_EVENT
- Per-project token breakdown — side-by-side Today/Month est. columns from JSONL exclusively; _col_pad() helper for Rich markup-aware alignment
- _fmt_tokens() with M/k/plain tiers for readable counts at any scale

### What Worked
- Mandatory Cloudflare spike in Phase 4 before writing any auth code — confirmed urllib.request and httpx both work; saved significant rework (no curl_cffi needed)
- Extend-not-replace principle: usage_fetcher.py, pool_state_manager.py, orchestrator.py, session_display.py all extended with optional kwargs — zero breaking changes
- TrayManager run_detached() pattern — avoids a 4th OS thread; race-free icon initialization with setup callback
- WebPoller daemon=True + Event.wait() — clean stop signal without join(); guaranteed thread death even if finally block is skipped
- Per-phase human smoke-test checkpoints caught alignment bugs (Phase 6 column padding) before they accumulated

### What Was Inefficient
- Phase 6 plan 04 required multiple deviation cycles (missing wire-up, then column alignment) — could have been caught with a more explicit integration test requirement in the plan
- REQUIREMENTS.md not updated at each phase transition — resulted in 13 unchecked requirements at milestone close (doc-sync gap, not missing work)
- 05-VERIFICATION.md and 06-VERIFICATION.md left as human_needed at close — acknowledged as deferred

### Patterns Established
- Extend-not-replace: new display rows always added as kwargs.get() blocks inside existing branches — never restructure the whole function
- _col_pad() for any column rendering with Rich markup or emoji — f-string :<N counts Python chars, not terminal columns
- WebPoller lifecycle pattern: daemon thread + Event.wait(N) + Event.set() stop; register via set_web_poller() before orchestrator.start()
- TrayManager lifecycle pattern: module-level shutdown helper, unconditional init+start, update at END of try block, stop with locals() guard in finally
- Corporate proxy pattern: SSL verify=False on httpx calls to match urllib.request behavior; document the reason inline

### Key Lessons
1. Spike Cloudflare behavior on the actual target machine before writing any auth/HTTP code — the spike paid for itself immediately
2. Update REQUIREMENTS.md at each phase transition, not retroactively at milestone close — 13 unchecked reqs at close created unnecessary close friction
3. _col_pad() is the correct pattern for any Rich terminal column layout — naive f-string padding will break on markup tags and wide emoji every time
4. Firefox-first cookie extraction is the reliable path — Chrome ABE (v127+) is a known failure mode; design the auth chain around Firefox as primary, Chrome as best-effort

### Cost Observations
- Model mix: predominately Sonnet (execution phases); Opus for research and planning phases
- Notable: yolo mode + coarse granularity removed nearly all confirmation gates, significantly reducing session overhead for a well-understood codebase

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 11 | Established base patterns (frozen dataclass, kwargs.get(), est. prefix) |
| v2.0 | +3 | +12 | Extend-not-replace discipline; mandatory pre-phase spikes; human smoke-test checkpoints |

### Cumulative Quality

| Milestone | Python LOC | Tests | Notes |
|-----------|-----------|-------|-------|
| v1.0 | ~3,000 est. | 31 | Core pipeline + display |
| v2.0 | ~8,731 | 70+ | Full stack: web + tray + per-project |

### Top Lessons (Verified Across Milestones)

1. **Spike unknown dependencies before planning** — verified by Cloudflare (v2.0), VTP/UTF-8 (v1.0)
2. **Extend-not-replace for display layers** — every v2.0 display feature added without breaking v1.0 paths
3. **Human smoke-test checkpoints catch what automated tests miss** — column alignment, tray behavior, live dashboard rendering
