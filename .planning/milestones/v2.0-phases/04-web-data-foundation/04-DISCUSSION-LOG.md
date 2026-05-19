# Phase 4: Web Data Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 04-web-data-foundation
**Areas discussed:** org_id setup, First-run auth UX, Credential migration, Web data display

---

## org_id setup

| Option | Description | Selected |
|--------|-------------|----------|
| Manual config.json | User sets org_id once in config.json. Same pattern as today. | |
| Auto-discover from API | Call a bootstrap/profile endpoint after auth to fetch org_id automatically. | |
| Prompt user at startup | If org_id missing, prompt interactively alongside sessionKey prompt. | ✓ |

**User's choice:** Prompt user at startup

**Follow-up — where to save org_id:**

| Option | Description | Selected |
|--------|-------------|----------|
| config.json | Write to ~/.claude-monitor/config.json — human-readable, easy to edit. | ✓ |
| keyring | Store in Windows Credential Manager alongside sessionKey. | |

**User's choice:** config.json

**Notes:** User added: "Also, try to make an API call first before firing the startup prompt to possibly avoid the user having to fetch this." → Final decision: attempt API auto-discovery first using the active sessionKey; only prompt the user for org_id if auto-discovery fails or no sessionKey is available yet.

---

## First-run auth UX

| Option | Description | Selected |
|--------|-------------|----------|
| Block startup, interactive prompt | Before launching dashboard, prompt user to paste sessionKey. One-time only — subsequent runs read from keyring. | ✓ |
| Launch degraded, prompt in background | Dashboard starts immediately in degraded mode with a setup instruction status row. Auth set up via --setup-auth flag separately. | |
| Silent degraded mode | Dashboard starts with no instructions. User must read README. | |

**User's choice:** Block startup, interactive prompt (Recommended)

**Follow-up — stale sessionKey handling:**

| Option | Description | Selected |
|--------|-------------|----------|
| Re-prompt automatically | 401/403 on first fetch → immediately show paste prompt again before launching. | ✓ |
| Silent fallback, re-prompt next launch | Fall back to "(est. — web unavailable)" for the session; clear stale key; prompt next launch. | |
| Show error row, no auto-prompt | Show "(web auth expired — run --reset-auth)" as status row. | |

**User's choice:** Re-prompt automatically (Recommended)

---

## Credential migration

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-migrate on startup | If session_key found in config.json: copy to keyring, delete from config.json, proceed. One-way, logged at INFO. | ✓ |
| Support both sources | Keyring priority + config.json fallback. No migration. | |
| Clean break | Only keyring; config.json session_key ignored. Users re-enter manually. | |

**User's choice:** Auto-migrate on startup (Recommended)

---

## Web data display

**Placement:**

| Option | Description | Selected |
|--------|-------------|----------|
| Replace P90 row, same section | Web data replaces P90 row in-place; INCLUDED/OVERAGE driven by web data; P90 fallback when unavailable. | ✓ |
| New section at top of dashboard | New "Web Usage" section above existing section; P90 section stays intact. Two sources visible. | |
| New rows below pool section | Additive — web rows at bottom; existing P90/pool section unchanged. | |

**User's choice:** Replace P90 row, same section (Recommended)

**Fallback behavior:**

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back to P90, labeled (est.) | Revert to P90-driven INCLUDED/OVERAGE with "(est. — web unavailable)" appended. Last sync time frozen. | ✓ |
| Show blank/dashes for web rows | Web rows show "-- — web unavailable". P90 section alongside. | |
| Hide web rows entirely | Dashboard looks exactly like Phase 3. No indication the web feature exists. | |

**User's choice:** Fall back to P90, labeled (est.) (Recommended)

---

## Claude's Discretion

- Exact Rich markup and emoji for new web data rows
- Whether `fetch_web_usage()` returns `WebUsageData` directly or `Optional[WebUsageData]`
- Error retry logic inside WebPoller (exponential backoff vs flat 300s interval)
- Whether org_id auto-discovery is its own function or inlined in auth setup flow

## Deferred Ideas

- curl_cffi Cloudflare bypass — conditional dep, only if httpx is blocked (spike first)
- Edge browser cookie extraction — behind Chrome in priority; not Phase 4 scope
- ANLX-02: pool balance from web API — not exposed by claude.ai
- Session reset model detection — may be discoverable from web API; capture during spike if possible
