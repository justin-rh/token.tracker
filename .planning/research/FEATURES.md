# Feature Landscape: Token Tracker v2.0

**Domain:** Developer tooling — Python terminal dashboard + Windows system tray for Claude Code usage
**Researched:** 2026-05-18
**Milestone focus:** v2.0 new capabilities only — browser cookie auth, claude.ai web data, system tray, hybrid data model, monthly reset, auto-refresh

---

## Feature 1: Browser Cookie Extraction

### What It Is

Read Chrome/Firefox/Edge cookies on Windows to get the `sessionKey` value for `claude.ai`, then use that cookie in Python `requests` calls to the usage endpoint. Automates what a user would do manually in DevTools.

### Table Stakes

| Behavior | Notes |
|----------|-------|
| Reads `sessionKey` cookie for `claude.ai` | The cookie is named `sessionKey`, has a `sk-ant-sid01-...` prefix |
| Chrome as primary browser | Most common; must work before touching Firefox/Edge |
| Fails gracefully to manual fallback | If extraction fails, print clear instruction: "Paste your sessionKey from DevTools" |
| Does not store the cookie in plaintext | Treat it as a runtime secret; use it in memory, don't write to config |

### Differentiators

| Behavior | Notes |
|----------|-------|
| Firefox fallback | `browser-cookie3` supports Firefox; Firefox uses SQLite + key4.db, no App-Bound encryption issue |
| Edge fallback | Chromium-based; same encryption problem as Chrome but different profile path |
| Friendly first-run setup guide | On first run, if auto-extract fails, print exact DevTools steps with a screenshot-friendly path: Settings → Application → Cookies → claude.ai |

### Anti-Features

| Anti-Feature | Reason |
|--------------|--------|
| Auto-refresh of cookie without user action | sessionKey is long-lived (days/weeks); re-reading on every poll is unnecessary noise against Chrome's encrypted store |
| Storing sessionKey in config.json in plaintext | Security risk. It grants full claude.ai account access. Use Windows Credential Manager or keep in memory only |
| Attempting to bypass App-Bound Encryption programmatically | Chrome v127+ uses App-Bound Encryption (SYSTEM-DPAPI wrapped key). browser-cookie3 is BROKEN for modern Chrome on Windows — do not attempt to work around it; fall back to manual paste |
| Supporting all browser profiles | Multiple profiles add path complexity. Default profile only. |

### Critical Complexity Note

**browser-cookie3 is effectively broken for Chrome v127+ on Windows.** Chrome switched to App-Bound Encryption in July 2024 (v127). browser-cookie3 v0.20.1 cannot decrypt these cookies. The library shows "Unable to get key for cookie decryption" errors on modern Chrome. Firefox does NOT have this issue — Firefox uses `key4.db` + a password, not DPAPI. Edge has the same problem as Chrome.

**Practical approach for v2.0:**
1. Try `browser-cookie3` against Firefox first (most reliable)
2. Try Chrome via `browser-cookie3` — it may work on machines that haven't updated Chrome past v126 or have the encryption bypass path available
3. If both fail, fall back to a one-time manual paste prompt: `Enter your claude.ai sessionKey (from DevTools > Application > Cookies):`
4. Cache the pasted value in Windows Credential Manager via `keyring` library (NOT in config.json)

**Confidence:** HIGH — App-Bound Encryption breakage confirmed in browser-cookie3 GitHub issues #210, #195, #180.

---

## Feature 2: claude.ai/settings/usage Data

### What It Is

The `claude.ai/settings/usage` page shows authoritative plan usage. The underlying `/usage` endpoint (undocumented) returns session-window and weekly utilization as percentages plus reset timestamps. Browser extensions (claude-counter, sshnox/Claude-Usage-Tracker, lugia19/Claude-Usage-Extension) have reverse-engineered this endpoint.

### What the Endpoint Returns (MEDIUM confidence — reverse-engineered, not officially documented)

```json
{
  "five_hour": {
    "utilization": 65,
    "resets_at": "2026-05-18T16:00:00+00:00"
  },
  "seven_day": {
    "utilization": 18,
    "resets_at": "2026-05-25T02:00:00+00:00"
  }
}
```

The `utilization` field is a percentage (0–100). Browser extensions report it is more precise than the rounded values shown on the visual page.

**Critical gap:** The endpoint reports utilization %, not raw token counts or dollar amounts. It does not expose the plan's absolute token limit, the overage pool balance, or per-project breakdown. For this project, utilization % is the primary value — it replaces the P90 inference with an authoritative "how full is my window" signal.

### How to Call It

```python
import requests

session = requests.Session()
session.cookies.set("sessionKey", "<sk-ant-sid01-...>", domain="claude.ai")

# GET organization ID first (needed for some endpoints)
orgs = session.get("https://claude.ai/api/organizations").json()
org_id = orgs[0]["uuid"]

# GET usage
usage = session.get("https://claude.ai/api/usage").json()
```

Some extensions also read org ID via `GET /api/organizations` and cache it for 24 hours. The `lastActiveOrg` cookie is an alternative source.

### Table Stakes

| Behavior | Notes |
|----------|-------|
| Fetch current 5-hour window utilization % | Replaces P90 inference with authoritative value |
| Fetch reset timestamp for current window | Replaces the estimated "resets in X hours" with exact countdown |
| Surface that this is web-sourced, not estimated | Label: "via claude.ai" instead of "est." prefix |

### Differentiators

| Behavior | Notes |
|----------|-------|
| Surface 7-day rolling utilization % alongside 5-hour | Useful context: are you burning unusually hard this week? |
| Cache the response and show "last refreshed at HH:MM:SS" | The endpoint should not be hammered; cache result, show staleness |

### Anti-Features

| Anti-Feature | Reason |
|--------------|--------|
| Polling the /usage endpoint more often than every 2–5 minutes | Undocumented endpoint; aggressive polling risks rate-limiting or ban |
| Treating utilization % as token count | Utilization is a ratio, not absolute. Applying it to a guessed limit to derive tokens is noise on top of noise |
| Scraping the HTML page instead of the API | Fragile; page structure changes break it. Use the JSON endpoint |
| Treating this as a billing source | The /usage endpoint shows session/weekly rate limit windows, NOT the $500 overage pool balance. Do not conflate |

### Monthly Reset Behavior

**Important:** The usage page billing model is more complex than "resets on the 1st." The Anthropic billing structure as of May 2026:

- **5-hour rolling window:** Resets every 5 hours from when it was first filled. NOT calendar-based.
- **7-day rolling window:** Resets 7 days after it was first filled.
- **Monthly subscription renewal:** The subscription billing date is when the plan's included usage quota resets. This is the date the user signed up, not necessarily the 1st.
- **Extra usage (overage pool):** Accumulates within the monthly billing cycle and is charged at renewal.

For the dashboard, "monthly reset" means resetting the locally-tracked pool spend accumulator at the start of each billing month. The billing cycle start date should be user-configurable (it already is per REQUIREMENTS.md OVGE-06).

**Confidence:** MEDIUM — billing structure from official Claude help docs; endpoint response format from reverse-engineered browser extensions.

---

## Feature 3: System Tray Icon

### What It Is

A persistent Windows system tray icon (notification area) that shows usage status at a glance without keeping the terminal open. Color changes based on utilization. Click opens/focuses the terminal dashboard. Right-click gives a context menu.

### Library Recommendation: pystray

`pystray` (not `infi.systray`) is the correct choice:
- Cross-platform API but Windows-native backend by default
- Supports dynamic icon update at runtime via `icon.icon = new_image`
- `run()` is blocking from main thread; use `threading.Thread(target=icon.run, daemon=True)` pattern since Windows does not require main-thread-only restriction (unlike macOS)
- Icon images are PIL `Image` objects — draw solid color circles with `ImageDraw` at runtime for color changes
- Latest version: 0.19.5 (active maintenance as of 2025)

`infi.systray` is Windows-only (acceptable for this project) but has a simpler API with less runtime flexibility — cannot update icon color dynamically as easily. Marked inactive (last release Jan 2025). Use `pystray`.

### Table Stakes

| Behavior | Notes |
|----------|-------|
| Persistent tray icon visible in notification area | Icon must appear when dashboard starts; survive terminal minimize |
| Green icon at <50% utilization | Solid circle, green |
| Yellow icon at 50–75% utilization | Solid circle, yellow |
| Red icon at >75% utilization | Solid circle, red |
| Tooltip shows current utilization % on hover | e.g., "Claude: 63% — resets in 2h 14m" |
| Right-click menu: "Open Dashboard", "Quit" | Minimum viable context menu |
| Icon disappears when dashboard quits | Clean exit required; lingering ghost icons are a UX failure |

### Differentiators

| Behavior | Notes |
|----------|-------|
| Left-click toggles terminal window focus | Single-click brings terminal to foreground or minimizes it |
| Tooltip includes last-refresh time | "Claude: 63% (updated 14s ago)" reduces "is this stale?" anxiety |
| Right-click menu: "Refresh Now" | Forces an immediate fetch instead of waiting for next poll cycle |
| Right-click menu: "Copy Status" | Pastes "Claude usage: 63%, resets in 2h 14m" to clipboard — useful for pasting into Slack |
| Animated icon when refresh is in progress | Brief spinner or pulsing during active HTTP fetch |

### Anti-Features

| Anti-Feature | Reason |
|--------------|--------|
| Balloon/toast notifications on every refresh | Intrusive. Notifications reserved for threshold crossings (INCLUDED → OVERAGE), not routine updates |
| Custom icon image file dependency | Using a solid-color circle drawn at runtime via PIL eliminates an asset dependency and makes color changes trivial |
| Windows startup entry (auto-launch at login) | Scope creep. Users can add it manually if desired. The dashboard itself is the entry point |
| Multiple icon instances | Guard against double-launch creating two tray icons |
| Pinning to taskbar | System tray (notification area) only — not the main taskbar |

### Threading Architecture

The tray must run in a background daemon thread. The Rich terminal dashboard owns the main thread (or its own loop). The tray thread reads utilization state from a shared data structure (a `threading.Event` + a simple `dataclass` behind a `threading.Lock`).

```
Main thread:    Rich dashboard loop (reads state, renders)
Thread 2:       Background poller (fetches web data, writes state)
Thread 3 (daemon): pystray tray icon (reads state, updates icon color)
```

**Confidence:** HIGH for pystray API behavior; HIGH for threading requirements; MEDIUM for the specific UX patterns (derived from Windows system tray conventions).

---

## Feature 4: Hybrid Data Model

### What It Is

Merge two data sources into a single unified usage view:
- **Authoritative web total:** `utilization %` + `resets_at` from `claude.ai/usage` endpoint
- **Local per-project breakdown:** token counts + cost estimates from JSONL files in `~/.claude/projects/`

The web source answers "how full is my window overall?" The local JSONL source answers "which project consumed what?"

### Table Stakes

| Behavior | Notes |
|----------|-------|
| Web utilization % drives the primary INCLUDED/OVERAGE indicator | Replaces P90 inference; authoritative |
| JSONL per-project table shows token/cost breakdown | Already in v1.0 reference tool; keep it |
| Graceful degradation: if web fetch fails, fall back to JSONL-only mode | Dashboard must not crash or go blank if the HTTP call fails |
| Clearly label data source in UI | "Window: 63% (via claude.ai)" vs "Projects: est. from local logs" |

### Differentiators

| Behavior | Notes |
|----------|-------|
| Reconciliation note when totals diverge significantly | If JSONL-derived estimate vs web utilization % are far apart, surface a note: "Local estimate may differ from authoritative data" |
| Per-project cost sorted by highest spend first | Makes it immediately obvious which project is burning the most |
| "Not yet synced" state while first fetch is in flight | Show a spinner, not stale/empty data |

### Anti-Features

| Anti-Feature | Reason |
|--------------|--------|
| Attempting to derive token counts from web utilization % | Utilization % has no mapping to absolute tokens without knowing the plan limit, which is not exposed |
| Using JSONL token counts to cross-validate web utilization | JSONL token counts are 100–174x undercounted; comparing them to utilization % creates noise, not insight |
| Hiding that the two sources are different | Must be transparent that INCLUDED/OVERAGE state comes from web and per-project breakdown comes from local files |
| Blocking the UI on web fetch | Web fetch should be async/background; dashboard renders with cached/stale data until fetch completes |

### Data Flow

```
On startup:
  1. Load JSONL per-project data (fast, local)
  2. Display immediately with JSONL-derived data
  3. Attempt web fetch in background thread
  4. On web fetch success: update utilization % and reset timestamp; refresh tray icon
  5. On web fetch failure: log error; continue with JSONL-only mode; show "Web data unavailable"

On subsequent polls (every 5 min):
  1. Reload JSONL (may have new entries)
  2. Attempt web fetch
  3. Merge and update display
```

**Confidence:** HIGH for the graceful degradation requirement; MEDIUM for the specific merge patterns.

---

## Feature 5: Monthly Reset

### What It Is

The locally-tracked overage pool accumulator (`pool_spend_usd` in `pool_state.json`) must reset at the start of each billing month. Without a reset, the running total grows indefinitely across months.

### Table Stakes

| Behavior | Notes |
|----------|-------|
| Auto-reset pool_spend_usd to 0.00 when a new billing month starts | Compare today's date to `monthly_period_start` in state file; if a new billing month has begun, reset |
| Billing cycle start day is user-configurable | Already in REQUIREMENTS.md OVGE-06. Default: 1 (first of month). User's actual renewal date may differ |
| Show "resets on [date]" in dashboard | Tells user when their included allocation and pool tracking will reset |

### Differentiators

| Behavior | Notes |
|----------|-------|
| Warn user before reset (e.g., last 3 days of cycle) | "Billing cycle resets in 2 days — pool spend will clear" |
| Show month-to-date pool spend vs prior month (if recorded) | Historical comparison: "This month: $94 vs last month: $147" |
| Manual --reset-pool CLI flag | Allows user to force-reset if they change plans or need to start fresh |

### Anti-Features

| Anti-Feature | Reason |
|--------------|--------|
| Assuming the 1st of the month is the billing date without confirming | The billing date is the subscription signup date, not always the 1st. Must be configurable, not hardcoded |
| Resetting silently with no log entry | Should write a log line: "Pool spend reset for new billing cycle (YYYY-MM-DD)" |
| Trying to read billing date from claude.ai | The billing date is not exposed in the /usage endpoint. User must configure it manually |

**Confidence:** HIGH for the reset mechanics; HIGH for the "must be configurable" requirement.

---

## Feature 6: Auto-Refresh

### What It Is

Background polling that re-fetches web usage data and re-reads JSONL files at a configurable interval, updating the dashboard and tray icon without user action.

### Table Stakes

| Behavior | Notes |
|----------|-------|
| Default polling interval: 5 minutes | 5 min is the standard referenced in PROJECT.md. Reasonable for an undocumented endpoint |
| Polling interval is user-configurable | Some users may want 1 min; some may want 15 min |
| Dashboard shows "last updated HH:MM:SS" | User must always be able to tell when data was last fetched |
| Polling does not block the display | Background thread; the UI renders continuously from cached state |

### Differentiators

| Behavior | Notes |
|----------|-------|
| Visual refresh indicator | Brief spinner or "refreshing..." text in a status line during active fetch |
| Adaptive backoff on 429 or connection error | If the web endpoint returns 429, back off to 15 min automatically, show "Rate limited — next refresh in 13m" |
| Jitter on poll interval | Add ±20 seconds of random jitter to avoid thundering-herd if multiple users run this on the same network |
| "Refresh Now" in tray right-click menu | Bypass wait without restarting the tool |

### Anti-Features

| Anti-Feature | Reason |
|--------------|--------|
| Polling the web endpoint more often than 1 minute | Risk of rate-limiting or IP ban on an undocumented endpoint |
| Hard-coding 5 minutes | Must be configurable; users have different tolerances for data staleness |
| Reloading the entire display on every poll | Only update the data-driven sections; avoid flicker by using Rich's Live context manager already in place |
| Showing a full loading screen during refresh | Background update should be invisible except for the "last updated" timestamp change |

### Implementation Pattern

Use `threading.Event` and a background thread with `event.wait(timeout=interval)`. This allows clean shutdown (set the event → background thread wakes up and exits) and does not require killing the thread:

```python
stop_event = threading.Event()

def poll_loop(stop_event, state, interval_seconds=300):
    while not stop_event.wait(timeout=interval_seconds):
        try:
            new_data = fetch_web_usage()
            with state.lock:
                state.update(new_data)
        except Exception as e:
            log.warning(f"Refresh failed: {e}")
```

**Confidence:** HIGH for the pattern; MEDIUM for the 5-minute default (pragmatic choice, not empirically derived).

---

## Feature Dependencies

```
Browser Cookie Auth ──────────────────────┐
                                           ▼
claude.ai Usage Data ──── depends on ─── Auth cookie
                                           │
                                           ▼
Hybrid Data Model ─────── depends on ─── Web data + JSONL reader (already built)
                                           │
                                           ▼
System Tray Icon ──────── reads from ──── Hybrid data model state
                                           │
Monthly Reset ─────────── feeds into ──── Pool spend accumulator (already built)
                                           │
Auto-Refresh ──────────── drives ────────┘ All of the above
```

**Critical path:** Auth cookie must work before any web data flows. If cookie auth fails permanently, the web data features degrade gracefully to JSONL-only — but the primary v2.0 value proposition (authoritative utilization %) is lost.

---

## MVP for v2.0

**Must ship (table stakes for this milestone):**
1. Manual sessionKey paste fallback for cookie auth (ensures v2.0 ships even if auto-extraction fails)
2. Web utilization % replaces P90 inference in the primary INCLUDED/OVERAGE indicator
3. Graceful fallback to JSONL-only if web fetch fails
4. pystray tray icon with 3-color system (green/yellow/red) and hover tooltip
5. 5-minute auto-refresh with background thread and "last updated" timestamp
6. Monthly pool spend auto-reset with configurable billing cycle start day

**Can defer:**
- Firefox/Edge cookie extraction (manual paste is sufficient for v2.0)
- Tray icon left-click window toggle (right-click menu is sufficient)
- Adaptive rate-limit backoff (manual interval config is sufficient)
- Historical monthly comparison

---

## Confidence Levels

| Area | Confidence | Reason |
|------|------------|--------|
| browser-cookie3 broken on Chrome v127+ Windows | HIGH | Confirmed in GitHub issues #210, #195, #180; security research confirms App-Bound Encryption change |
| sessionKey cookie name and format | HIGH | Multiple reverse-engineered clients confirm `sk-ant-sid01-...` in `sessionKey` cookie |
| /usage endpoint response structure | MEDIUM | Reverse-engineered by browser extensions; not officially documented; may change |
| pystray threading model on Windows | HIGH | Official pystray docs confirm Windows does not require main-thread restriction |
| 5-hour rolling window (not calendar day) reset model | HIGH | Confirmed in official Claude help docs and multiple GitHub issues |
| Monthly billing date = signup date (not 1st) | HIGH | Confirmed in Anthropic billing FAQ |
| browser-cookie3 works on Firefox | MEDIUM | Firefox uses different encryption model (not App-Bound); library has Firefox support; not tested on this specific machine |

---

## Sources

- [browser-cookie3 PyPI](https://pypi.org/project/browser-cookie3/)
- [browser-cookie3 GitHub issues — Chrome encryption breakage](https://github.com/borisbabic/browser_cookie3/issues/210)
- [pystray documentation](https://pystray.readthedocs.io/en/latest/usage.html)
- [pystray PyPI](https://pypi.org/project/pystray/)
- [Google Chrome App-Bound Encryption announcement (July 2024)](https://security.googleblog.com/2024/07/improving-security-of-chrome-cookies-on.html)
- [sshnox/Claude-Usage-Tracker — GET /api/organizations pattern](https://github.com/sshnox/Claude-Usage-Tracker)
- [she-llac/claude-counter — /usage endpoint + SSE stream](https://github.com/she-llac/claude-counter)
- [lugia19/Claude-Usage-Extension](https://github.com/lugia19/Claude-Usage-Extension)
- [Manage extra usage for paid Claude plans (official)](https://support.claude.com/en/articles/12429409-manage-extra-usage-for-paid-claude-plans)
- [Paid Plan Billing FAQs (official)](https://support.claude.com/en/articles/8325618-paid-plan-billing-faqs)
- [Claude usage limits — 5-hour rolling window (fuelgauge.pro guide)](https://fuelgauge.pro/guides/claude-usage-limits/)
- [Python threading.Event documentation](https://docs.python.org/3/library/threading.html)
