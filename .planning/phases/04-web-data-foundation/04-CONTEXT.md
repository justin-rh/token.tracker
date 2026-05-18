# Phase 4: Web Data Foundation - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Authenticate with claude.ai via browser cookies or manual sessionKey, fetch authoritative 5-hour window utilization % and reset countdown, display it in the terminal dashboard, and poll every 5 minutes in the background. Graceful fallback to P90-based estimates when web data is unavailable. No system tray in this phase — that is Phase 5.

</domain>

<decisions>
## Implementation Decisions

### org_id Configuration
- **D-01:** org_id is stored in `~/.claude-monitor/config.json` (key: `org_id`). On startup, Phase 4 first attempts to auto-discover org_id by calling a bootstrap/profile endpoint using the active sessionKey. If auto-discovery succeeds, the discovered org_id is written to config.json. If auto-discovery fails (no sessionKey yet, or API error), prompt the user to enter org_id at the console before launching the dashboard and save it to config.json.
- **D-02:** If `org_id` is already present in config.json, skip discovery entirely — use the stored value directly.

### Credential Storage (AUTH-02/03)
- **D-03:** sessionKey is stored exclusively in **Windows Credential Manager via `keyring`** — never written to plaintext config.json. Service name: `claude-monitor`, username: `sessionKey`.
- **D-04:** **Auto-migration on startup:** If `session_key` (or `cf_clearance`) is found in config.json, copy to keyring, delete from config.json, and proceed. This is a one-way migration — logged at INFO level. No user prompt required.
- **D-05:** `cf_clearance` cookie (if needed for Cloudflare): also stored in keyring (username: `cf_clearance`). Same auto-migrate pattern from config.json.

### Cookie Extraction Order (AUTH-01)
- **D-06:** Auth resolution priority:
  1. keyring (Windows Credential Manager) — always checked first
  2. Firefox cookie store — primary auto-extraction source
  3. Chrome cookie store — best-effort; may fail on Chrome 127+ due to App-Bound Encryption; only attempted when Chrome is NOT running
  4. Manual paste prompt — fallback when all above fail
- **D-07:** Firefox cookie extraction is **new code** in Phase 4. The existing Chrome extraction in `usage_fetcher.py` is kept but moved to position 3. Firefox uses `browser-cookie3` library for the cookies.sqlite file.

### First-Run Auth Prompt (AUTH-02)
- **D-08:** When no sessionKey is available from keyring or any browser (and org_id is also unknown), **block the dashboard launch** and show an interactive console prompt:
  ```
  Web auth required.
  1. Open chrome.ai in your browser
  2. Open DevTools (F12) → Application → Cookies → claude.ai
  3. Copy the value of the 'sessionKey' cookie

  Paste sessionKey here: _
  ```
  User pastes the value and presses Enter. The key is saved to keyring. Dashboard then launches.
- **D-09:** If org_id is also unknown at this point, prompt for org_id immediately after the sessionKey prompt (same blocking flow). Attempt API auto-discovery first — only ask the user if that fails.
- **D-10:** **Stale key re-prompt:** If a stored sessionKey returns 401 or 403 on the first API call of a new session, immediately show the paste prompt again before launching the dashboard (same flow as D-08). The stale key is cleared from keyring before prompting.
- **D-11:** Once auth is configured successfully, subsequent launches read from keyring without any prompt (AUTH-03).

### WebPoller Threading (POLL-01)
- **D-12:** `monitoring/web_poller.py` is a new module. `WebPoller` is a daemon thread using `threading.Event` for the 300-second sleep (not `time.sleep`). A `threading.Lock` protects the cached `WebUsageData` result.
- **D-13:** The poller calls `usage_fetcher.fetch_web_usage()` every 5 minutes. On success, it updates the cache and records `last_sync_time`. On failure, it logs a warning and leaves the last successful cache value intact (graceful degradation).
- **D-14:** `monitoring/orchestrator.py` gets a `set_web_poller()` method. The poller is started in `cli/main.py` alongside the monitoring thread; both are stopped in the existing `finally` block.

### Web Data Model
- **D-15:** Add `WebUsageData` as a frozen dataclass to `core/models.py`:
  - `utilization_pct: float` — 5-hour window utilization %
  - `reset_at: datetime` — when the current 5-hour window resets (UTC)
  - `fetched_at: datetime` — when this data was retrieved
  - `plan_limit_tokens: Optional[int]` — actual plan limit from web API (replaces P90 when available)
- **D-16:** `monitoring/orchestrator.py` exposes `web_usage` key in `monitoring_data` dict passed to callbacks. Value is `Optional[WebUsageData]`.

### Display Integration (WEBD-01, WEBD-02, WEBD-03)
- **D-17:** When `web_usage` is available: the existing P90 threshold row is **replaced in-place** with:
  - `Utilization: 67%  via claude.ai`
  - `Resets in: 1h 23m`
  The INCLUDED/OVERAGE label is driven by `web_usage.utilization_pct` (≥100% = OVERAGE). The pool section (Phase 3) uses this web-sourced classification.
- **D-18:** When `web_usage` is `None` (unavailable): revert to Phase 2/3 P90-driven INCLUDED/OVERAGE display, appending `(est. — web unavailable)` to the threshold row label. The P90 calibration display (`Calibrating N/10`) also shows when web data is absent and P90 hasn't calibrated.
- **D-19:** `Last web sync: HH:MM:SS` — shown as a footer row in the threshold section after the first successful fetch. Frozen at the last success time when web data is unavailable.
- **D-20:** `session_display.py` receives `web_usage: Optional[WebUsageData]` via `kwargs`. Existing `kwargs.get("threshold_state")` and `kwargs.get("pool_state")` patterns are unchanged.

### HTTP Client (WEBD-03)
- **D-21:** Default HTTP client is `httpx` (sync, used inside the WebPoller daemon thread). `curl_cffi` is a **conditional dependency** — add to `pyproject.toml` as an optional extra (`[extras]`) or upgrade path only if httpx is blocked by Cloudflare. Do not pre-add. The planner should spike httpx first on the target machine.
- **D-22:** Use `.get("key", default)` for all JSON field access on the claude.ai API response. Log the raw response at DEBUG level. No assumptions about response schema stability.

### API Endpoint (WEBD-01)
- **D-23:** `fetch_web_usage()` is a new function in `core/usage_fetcher.py`. The planner/researcher must discover (via spike on the actual machine) which claude.ai API endpoint returns the 5-hour window utilization % and reset time. Likely candidate: `GET /api/organizations/{org_id}/usage` (already used for pool spend) or a separate real-time endpoint. **Spike this first before writing any parsing code.**

### Billing Cycle Reset Logging (POLL-02)
- **D-24:** On the configured billing cycle start day, the existing `pool_state_manager.py` already handles resetting pool spend. Phase 4 adds a console log event: `[INFO] Billing cycle reset — pool spend cleared to $0.00`. No changes to the reset logic itself.

### Claude's Discretion
- Exact Rich markup and row layout for web data rows — consistent with existing session_display.py style
- Whether `fetch_web_usage()` returns `WebUsageData` directly or wraps it in an `Optional`
- Error retry logic inside WebPoller (e.g., exponential backoff vs flat interval)
- Whether org_id auto-discovery gets its own function in `usage_fetcher.py` or is inlined in the auth setup flow

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 Requirements
- `.planning/REQUIREMENTS.md` — AUTH-01, AUTH-02, AUTH-03, WEBD-01, WEBD-02, WEBD-03, POLL-01, POLL-02 are the full scope. Read for exact acceptance criteria.

### Prior Phase Context
- `.planning/phases/03-overage-pool-dashboard/03-CONTEXT.md` — D-12/D-13: display layout and "est." prefix pattern. D-03/D-06: pool_spend.json and billing cycle patterns (POLL-02 extends these). Phase 4 replaces the P90 row built in Phase 2 (D-09/D-10) when web data is available.
- `.planning/phases/02-threshold-detection/02-CONTEXT.md` — D-03/D-04: config.json location and key naming. D-09/D-10: INCLUDED/OVERAGE status row — Phase 4 replaces the source of this classification.
- `.planning/phases/01-windows-foundation/01-CONTEXT.md` — D-03: Windows AppData path. D-06/D-07: statusline.jsonl cost source (still used for pool spend; JSONL-based rows remain unchanged).

### Source Files (Key Integration Points)
- `core/usage_fetcher.py` — Add `fetch_web_usage() -> Optional[WebUsageData]`; add Firefox cookie extraction; add org_id auto-discovery; migrate Chrome extraction to position 3 in priority order. Auto-migrate config.json credentials to keyring here.
- `core/models.py` — Add `WebUsageData` frozen dataclass (D-15).
- `monitoring/orchestrator.py` — Add `set_web_poller()`; add `web_usage` key to `monitoring_data`.
- `ui/session_display.py` — Add web data rows via `web_usage` kwarg; replace P90 row when web data available (D-17/D-18/D-19).
- `cli/main.py` — Instantiate and start `WebPoller`; wire into orchestrator; stop in `finally` block.
- `core/pool_state_manager.py` — Accept optional `web_usage` param; use `web_usage.utilization_pct` to drive INCLUDED/OVERAGE when present (STATE.md decision).

### Project State
- `.planning/STATE.md` — Architecture notes section: threading model, module extension list, and Cloudflare warning. Read before planning.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/usage_fetcher.py:_read_auth_cookies()` — Existing Chrome extraction + config.json read. Phase 4 refactors this to add Firefox (position 2) and keyring (position 1), keeping Chrome as position 3.
- `core/usage_fetcher.py:fetch_pool_spend_usd()` — Existing HTTP call to `/api/organizations/{org_id}/usage`. Phase 4 `fetch_web_usage()` follows the same pattern (same auth, same URL, likely same endpoint or a related one).
- `ui/session_display.py:_render_wide_progress_bar()` — Reusable Rich progress bar. Utilization % bar for the web data row.
- `monitoring/orchestrator.py:MonitoringOrchestrator` — Existing threading model: `threading.Event`, `threading.Thread` daemon. WebPoller mirrors this pattern exactly.
- `core/pool_state_manager.py` / `core/threshold_manager.py` — Established frozen dataclass + factory function pattern. `WebUsageData` and `fetch_web_usage()` follow this convention.

### Established Patterns
- config.json in `~/.claude-monitor/` for all user-editable settings
- `kwargs.get("threshold_state")` / `kwargs.get("pool_state")` for passing state to session_display.py — Phase 4 adds `kwargs.get("web_usage")`
- Atomic file writes: `.tmp` → `rename()` (config.json updates)
- `threading.Event` stop signal for daemon threads
- All JSONL-derived figures labeled "est."; web-sourced figures labeled "via claude.ai"

### Integration Points
- `cli/main.py` — Start WebPoller before the Rich Live loop; pass to orchestrator; stop in `finally`
- `monitoring/orchestrator.py:_monitoring_loop()` — Include `web_usage` in the `monitoring_data` dict on each callback
- `ui/session_display.py:format_active_session_screen()` — Read `web_usage` from kwargs; branch on `web_usage is not None`

</code_context>

<specifics>
## Specific Ideas

- First-run prompt phrasing (D-08): "Open DevTools (F12) → Application → Cookies → claude.ai → copy sessionKey value" — matches Chrome DevTools navigation
- Row format when web data available (D-17): `"🌐 [value]Utilization:[/]   67%  via claude.ai"` and `"⏱ [value]Resets in:[/]     1h 23m"`
- Row format when web data absent (D-18): `"🔢 [value]Token limit:[/]   88,000 (P90) (est. — web unavailable)"`
- Last sync footer (D-19): `"🔄 [dim]Last web sync: 14:32:07[/]"` — dimmed to reduce visual weight
- keyring service name: `claude-monitor`, usernames: `sessionKey` and `cf_clearance`

</specifics>

<deferred>
## Deferred Ideas

- **curl_cffi Cloudflare bypass** — Only add if httpx is blocked on the target machine. Do not pre-add. Evaluate during the spike.
- **Multi-browser cookie extraction** (Edge) — Edge uses Chromium profile path; can be added as position 4 behind Chrome. Not in Phase 4 scope.
- **ANLX-02: Overage pool balance from web API** — claude.ai usage endpoint returns utilization % only; pool balance not exposed. Deferred to v2.1.
- **Session reset model detection** (from Phase 3 deferred) — Web API may clarify whether it's rolling 5-hour windows or calendar-day. If discoverable during the Cloudflare/endpoint spike, capture it; otherwise defer.

</deferred>

---

*Phase: 04-web-data-foundation*
*Context gathered: 2026-05-18*
