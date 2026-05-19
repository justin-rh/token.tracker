# Milestones

## v1.0 — Windows Foundation + Overage Pool Dashboard

**Completed:** 2026-05-08
**Phases:** 3 (11 plans)

**What shipped:**
- Fork of Claude-Code-Usage-Monitor running correctly on Windows (APPDATA path, requestId dedup, VTP/UTF-8 rendering)
- P90 threshold detection with cold-start guard (10-session minimum)
- Overage pool dashboard: INCLUDED/OVERAGE status, est. pool spend, progress bar, burn rate, exhaustion projection
- pool_spend.json persistence across restarts
- Pool size and billing cycle start day configurable via config

**Key decisions logged in PROJECT.md.**

---

## v2.0 — Web-Sourced Usage + System Tray

**Completed:** 2026-05-19
**Phases:** 6 total (v1.0: 1–3, v2.0 extensions: 4–6) | **Plans:** 23

**What shipped:**
- claude.ai web integration — Firefox/Chrome cookie extraction, keyring storage, WebPoller daemon thread (5-min interval), authoritative 5-hour utilization % and reset time in terminal dashboard
- Color-coded system tray icon (green <50%, yellow 50–75%, red ≥75%) via pystray + Pillow — tooltip with utilization % + last sync time, right-click menu (Open Dashboard / Quit), left-click window toggle, clean shutdown with no ghost icons
- Per-project token breakdown — side-by-side Today (est.) / This month (est.) columns sourced exclusively from JSONL; _col_pad() helper for Rich markup-aware alignment
- Full data pipeline: WebPoller → monitoring_data → display_controller → session_display, with graceful fallback to "(est. — web unavailable)" on any fetch failure
- D-24 billing cycle reset detection with INFO log in pool_state_manager.py

**Timeline:** 2026-05-07 → 2026-05-19 (12 days)
**LOC:** ~8,731 Python source (excl. tests) | 151 files changed | 32,132 insertions

**Key decisions logged in PROJECT.md.**

Known deferred items at close: 3 acknowledged (see STATE.md Deferred Items)
