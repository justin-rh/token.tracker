# Pitfalls: v2.0 Additions to Claude Token Tracker

**Domain:** Adding browser cookie auth, claude.ai web fetching, and system tray to an existing
Python Windows terminal dashboard
**Researched:** 2026-05-18
**Milestone:** v2.0 Web-Sourced Usage + System Tray

This file replaces the v1.0 PITFALLS.md for features added in v2.0. v1.0 pitfalls (path handling,
Rich rendering, JSONL parsing, P90 detection) remain valid for the existing codebase and are
documented in the git history. This file covers only the new v2.0 feature areas.

---

## Area 1: Browser Cookie Extraction on Windows

### CRITICAL — Chrome v127+ App-Bound Encryption Breaks Simple DPAPI Decryption

**What goes wrong:** Before Chrome v127 (July 2024), any Python script running as the same
Windows user could call `CryptUnprotectData` via `pywin32` to decrypt the AES key stored in
Chrome's `Local State` file. Chrome v127 introduced "app-bound encryption" (ABE): the AES key
is now encrypted a second time by a SYSTEM-level Chrome service that verifies the calling
process is Chrome itself. A plain `pywin32.CryptUnprotectData()` call on the `encrypted_key`
field returns an error or garbage bytes on Chrome v127+. Libraries like `browser-cookie3` and
`pycookiecheat` that were not updated for ABE will silently return empty cookie jars or
malformed bytes without raising an explicit error.

**Why it happens:** The `encrypted_key` in `%LOCALAPPDATA%\Google\Chrome\User Data\Local State`
now has a v20 prefix instead of v10/v11. The v20 prefix signals ABE-protected data that requires
the `IElevator` COM interface (available only to the Chrome process).

**Consequences:** Cookie extraction returns zero cookies, or the sessionKey cookie is missing.
The web fetch phase never receives a valid session, so it falls back to JSONL-only data silently.
This is a hard blocker on the primary v2.0 data source if Chrome is the only supported browser.

**Prevention:**
1. Check `browser-cookie3` version. As of 2025, version 0.19.1+ added a Windows ABE workaround
   using a temporary copy of the Cookies database opened via SQLite URI read-only mode. Pin to
   this version or later and verify the workaround is active.
2. Implement a graceful fallback chain: Chrome ABE failure → Edge (also Chromium-based, same
   ABE problem but may have different timing) → Firefox (unencrypted cookies.sqlite, no ABE).
3. On failure, surface a user-visible message: "Chrome cookie extraction failed — try Firefox or
   Edge." Do not silently use JSONL-only data without telling the user.
4. Test against the actual installed Chrome version on the target machine before shipping. The
   ABE bypass that works in lab testing may be patched by the time the feature ships.

**Phase:** Cookie extraction phase (Phase 4 or whatever phase introduces web fetch). Must be
validated with live Chrome on the user's machine before declaring the phase complete.

---

### CRITICAL — Chrome Cookies Database Locked While Chrome Is Running

**What goes wrong:** Chrome holds an exclusive write lock on
`%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cookies` while running. A direct `sqlite3.connect()`
call raises `sqlite3.OperationalError: database is locked`. This is the same `WinError 32`
file-sharing violation pattern that hit JSONL reading in v1.0, but SQLite is less forgiving than
Python's `open()` — there is no equivalent of `os.O_RDONLY` that bypasses the lock cleanly.

**Why it happens:** Chrome uses WAL (Write-Ahead Logging) mode and holds shared-memory files
(`.shm`, `.wal`) alongside the main `.db`. Even if the main file opens, reading without the
WAL pages produces stale or incomplete data.

**Prevention:**
1. Open the Cookies database using SQLite's URI read-only mode with `immutable=1`:
   `sqlite3.connect("file:///...Cookies?immutable=1&mode=ro", uri=True)`. The `immutable=1`
   flag tells SQLite to skip the WAL and treat the file as read-only, bypassing the lock.
2. Alternatively, copy the Cookies file (and `.shm`/`.wal` files if present) to a temp
   directory before opening. This is the approach `browser-cookie3` uses internally.
3. Never open the live Cookies file in write mode. Even accidental journal creation corrupts
   Chrome's database.

**Phase:** Cookie extraction. Must be the first thing tested with Chrome open.

---

### MODERATE — Cookie Staleness: Chrome Refreshes Cookies Without Writing to Disk Immediately

**What goes wrong:** Chrome caches cookies in memory and only flushes to the SQLite database
periodically or on browser close. A cookie you can see in Chrome DevTools (the live, in-memory
value) may differ from what is in the `Cookies` database file at the moment your script reads it.
The `sessionKey` for claude.ai may appear valid from the file but be stale if Anthropic rotated
it in the current session.

**Prevention:**
1. After a successful web fetch with the extracted cookie, store the timestamp. If the next
   fetch fails with HTTP 401/403, re-extract the cookie rather than assuming the stored value
   is permanent.
2. Implement a retry-with-reextract path: on auth failure, reload cookie from disk, retry once.
   If still failing, surface an error rather than looping.
3. Do not cache the extracted cookie in a config file or persistent store. Always extract fresh
   at startup and on auth failure.

**Phase:** Cookie extraction + web fetch integration. Both phases must understand the retry flow.

---

### MODERATE — Firefox Cookie Extraction Complexity (Key4.db + NSS Decryption)

**What goes wrong:** Firefox cookies are not encrypted at the cookie-value level (unlike Chrome),
but the `cookies.sqlite` is still locked when Firefox is running. More critically, if Firefox
is the fallback path, the implementation complexity is non-trivial: NSS key derivation from
`key4.db` is required only for passwords, not cookies. Cookie values in Firefox `cookies.sqlite`
are plain text — but this is easy to get wrong by assuming the Chrome decryption path applies.

**Prevention:**
1. For Firefox cookies, open `%APPDATA%\Mozilla\Firefox\Profiles\<random>.default\cookies.sqlite`
   using the same URI read-only + immutable approach as Chrome.
2. Do not apply DPAPI decryption to Firefox cookie values. They are stored as plain text in the
   `value` column of the `moz_cookies` table. Applying decryption to them produces garbage.
3. Use `browser-cookie3` for the Firefox path as well — it handles the profile discovery glob
   and read-only open correctly.

**Phase:** Cookie extraction fallback path. Only triggered if Chrome ABE fails.

---

### MINOR — Edge Uses the Same ABE System as Chrome

**What goes wrong:** Microsoft Edge is Chromium-based and introduced its own app-bound encryption
that mirrors Chrome's. Edge cookies live in `%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cookies`.
Using Edge as a "fallback from Chrome" does not escape the ABE problem — you simply encounter
it in a slightly different file path.

**Prevention:** Treat Edge as a peer to Chrome in terms of complexity, not a simpler fallback.
If implementing Edge support, use the same ABE-aware approach as Chrome. Firefox remains the
genuinely simpler fallback.

**Phase:** Cookie extraction. Important when scoping browser priority.

---

## Area 2: Fetching claude.ai With Cookies

### CRITICAL — claude.ai Is a JavaScript SPA; `requests` Returns Empty Shell HTML

**What goes wrong:** `claude.ai/settings/usage` is a React single-page application. A plain
`requests.get("https://claude.ai/settings/usage")` returns the raw HTML shell (the `<div id="root">`
container) with no usage data. The actual usage numbers are populated by a JavaScript bundle that
makes its own API calls after the page loads. The `requests` response will look like a valid 200
OK with HTML, but no token counts, no plan limits, no billing data will be present in the body.

**Why it happens:** React apps load data asynchronously via XHR/fetch after the initial HTML is
delivered. `requests` executes no JavaScript.

**Consequences:** The parser finds no data, returns None or empty dict, and the hybrid layer
silently falls back to JSONL-only totals. This looks like a working feature because the app
keeps functioning — but the web-sourced data path is completely dead.

**Prevention:**
1. Before writing any fetch code, open Chrome DevTools → Network tab → XHR filter, then
   navigate to `claude.ai/settings/usage`. Identify the specific JSON API endpoint that the
   page calls (likely something under `claude.ai/api/` or a similar internal REST path).
2. If a JSON API endpoint is discoverable, hit it directly with `requests` and the session
   cookie. This is simpler than Playwright and does not require a browser.
3. If no direct API endpoint exists or is too fragile, use `playwright-stealth` + Playwright
   to render the page and extract the data after `networkidle`.
4. Document which approach was chosen and why in `STATE.md` as a key decision. This is the
   highest-uncertainty technical question in v2.0.

**Phase:** Web fetch phase. Research (discovering the API endpoint via DevTools) must happen
before writing any code. Do not write a `requests`-based parser without first confirming
the endpoint exists and returns JSON.

---

### CRITICAL — Cloudflare Bot Detection May Block Headless Python Requests

**What goes wrong:** `claude.ai` is behind Cloudflare. Cloudflare's bot detection checks
TLS fingerprints, HTTP/2 frame ordering, browser-specific request headers, and JavaScript
challenge completion. A Python `requests` call with a standard `User-Agent` header has a
distinctive TLS fingerprint that Cloudflare can identify as a non-browser client, returning
403 or a JS challenge page even with a valid session cookie.

**Confirmed instance:** GitHub issue anthropics/claude-code#39896 documents that Claude Code's
own `WebFetch` tool fails on `claude.ai` specifically due to Cloudflare bot protection blocking
headless domain verification requests.

**Consequences:** Every web fetch attempt returns HTTP 403 or redirects to a Cloudflare
interstitial page. The app gets no web data ever, and must fall back to JSONL permanently.
This is not intermittent — it is consistent and user-visible.

**Prevention:**
1. Use `curl_cffi` instead of `requests`. `curl_cffi` uses libcurl compiled with BoringSSL and
   can impersonate a real browser's TLS fingerprint (Chrome 120, Chrome 124, etc.), bypassing
   most Cloudflare TLS checks: `pip install curl-cffi`.
2. Pass realistic browser headers: `User-Agent`, `Accept`, `Accept-Language`, `Sec-Fetch-*`,
   `sec-ch-ua`. Extract these from a real Chrome DevTools network trace.
3. If even `curl_cffi` is blocked, use Playwright with the user's actual Chrome profile
   (`--user-data-dir`), which already has the Cloudflare trust tokens from prior browser use.
4. Test on the actual target machine, not in a CI environment. Cloudflare behavior differs by
   IP reputation, and corporate networks may have different treatment than residential IPs.

**Phase:** Web fetch phase. Must be the first test run before any parsing code is written.

---

### CRITICAL — API Shape Is Undocumented and Can Change Without Notice

**What goes wrong:** The claude.ai usage endpoint is an internal, undocumented API. Anthropic
can change its request format, response schema, URL path, or authentication mechanism at any
time without notice, since it is not a public API. A v2.0 feature that works today may silently
return wrong data or crash after an Anthropic product update.

**Consequences:** After an Anthropic UI update, the web fetch returns 404 or returns data in a
changed JSON shape. The parser raises a `KeyError` or returns None, and the app falls back to
JSONL silently. Users see no error; data is just wrong or missing.

**Prevention:**
1. Wrap all web-fetch parsing in `try/except` with explicit logging of unexpected response
   shapes. Never use `response["key"]` on undocumented API responses — always use
   `.get("key", default)` with a fallback.
2. Log the raw response (at DEBUG level) on every fetch so unexpected schema changes are
   diagnosable from logs without needing a repro.
3. Version-detect the response: check for the presence of expected keys before parsing. If keys
   are absent, log a warning "Web data schema changed — check claude.ai API" and fall back to
   JSONL. This surfaces the breakage to the user without crashing.
4. When implementing, add a `WEB_DATA_SCHEMA_VERSION` constant to note the schema captured
   during development. Include the date in a comment so staleness is detectable.

**Phase:** Web fetch phase and ongoing maintenance. Schema changes will recur.

---

### MODERATE — Session Expiry: sessionKey Cookie Has Unknown Expiration

**What goes wrong:** The `sessionKey` cookie on `claude.ai` expires after inactivity or an
explicit re-auth event. The exact TTL is not publicly documented but appears to be on the order
of days to weeks. A user who logs into Claude.ai infrequently may find their stored session
cookie has expired by the time the tracker polls it. The failed request returns HTTP 401, the
tracker falls back to JSONL, and the user has no idea why the web data stopped working.

**Prevention:**
1. On every web fetch, check the HTTP response status. If 401 or 403, set a flag
   `web_fetch_auth_failed = True` and display a persistent indicator in the dashboard:
   "Web data unavailable — log into claude.ai in your browser to refresh."
2. Re-attempt cookie extraction at each startup (not just first run) so a fresh browser
   session automatically restores the web fetch path.
3. Do not store the extracted cookie in a config file. Always re-extract from the browser's
   Cookies database at startup. The browser is the source of truth for session validity.

**Phase:** Web fetch phase + hybrid data layer. The "log in again" recovery path must be
wired before the phase is considered complete.

---

### MODERATE — Rate Limiting from Polling Every 5 Minutes

**What goes wrong:** Polling claude.ai every 5 minutes means 288 requests per day from a single
user. Anthropic's internal APIs likely have rate limits that are not documented. Exceeding them
could result in temporary 429 responses, or worse, account flags on the user's Anthropic account.

**Prevention:**
1. Cache the last successful web response with a timestamp. Only issue a new HTTP request if
   the cache is older than the configured interval (default 5 minutes). Do not bypass the cache
   during normal operation.
2. On a 429 response, implement exponential backoff starting at 30 seconds and increasing to a
   max of 30 minutes. Log the backoff clearly.
3. Consider making the polling interval user-configurable and defaulting to 15 minutes instead
   of 5 minutes. Usage totals do not change second-by-second; 15-minute resolution is accurate
   enough for the dashboard's purpose.

**Phase:** Web fetch phase + background polling phase.

---

## Area 3: System Tray With pystray

### CRITICAL — pystray `run()` Is Blocking; Must Not Be Called From the Main Thread If Rich Live Is Also Running There

**What goes wrong:** `pystray.Icon.run()` is a blocking call that enters the Windows message
loop (via `win32gui`). If called from the main thread, it blocks all other main-thread activity
permanently. The existing app uses the main thread for the Rich `Live` display loop (see
`cli/main.py`, which calls `live_display.__enter__()` and then `while True: time.sleep(1)`
as the Windows-safe fallback for `signal.pause()`). Calling `pystray.Icon.run()` from that same
flow would never reach the Rich loop.

**Why it happens:** The existing Windows main-loop fallback (`while True: time.sleep(1)`) is
itself blocking. Neither pystray nor Rich's Live display will run if the other occupies the
main thread.

**Prevention:**
1. Use `pystray.Icon.run_detached()` instead of `run()`. `run_detached()` prepares the Win32
   message loop in background infrastructure without blocking the calling thread, then returns
   immediately. The calling code can then proceed to the Rich Live loop. Call `icon.stop()` to
   clean up.
2. Do not call `pystray.Icon.run()` from a `threading.Thread`. While this works on Windows
   (unlike macOS, where it fails), it is fragile: if the thread is a daemon thread and the main
   thread exits, the tray icon disappears without cleanup, leaving a ghost entry in the taskbar
   that requires an Explorer restart to clear.
3. Recommended architecture: `run_detached()` on the main thread before entering the Rich Live
   loop, then `icon.stop()` in the cleanup block that already calls `orchestrator.stop()`.

**Phase:** System tray phase. Architecture decision must be made before any pystray code is
written.

---

### CRITICAL — Tray Icon Image Must Be a Pillow `Image` Object, Not a File Path

**What goes wrong:** `pystray.Icon` requires a `PIL.Image.Image` object for the `icon` parameter.
Passing a string file path or a bytes object raises `AttributeError` or `TypeError` at icon
creation time. Most code examples online show `Image.open("icon.png")`, but this requires the
file to exist at that path at runtime — which it will not if the icon is a package resource
embedded in the installed wheel.

**Prevention:**
1. Generate the icon programmatically using Pillow rather than loading from disk. A solid-color
   circle or square with a letter "T" renders fine at system tray size (16x16 or 32x32) and
   requires no file:
   ```python
   from PIL import Image, ImageDraw
   def make_tray_icon(color: str) -> Image.Image:
       img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
       draw = ImageDraw.Draw(img)
       draw.ellipse([4, 4, 28, 28], fill=color)
       return img
   ```
2. Store the icon only as an in-memory `Image` object. Never write it to disk and read it back.
3. To update the icon color (green/yellow/red for tray indicator), call `icon.icon = make_tray_icon("red")`
   on the existing icon object. This updates the tray without destroying and recreating the icon.

**Phase:** System tray phase.

---

### MODERATE — Icon Update From the Monitoring Thread Requires Thread-Safe Access

**What goes wrong:** The monitoring orchestrator runs in `_monitor_thread` (see `orchestrator.py`
line 54: `threading.Thread(target=self._monitoring_loop, ...)`). Calling `icon.icon = new_image`
from inside the monitoring callback dispatches a Win32 window message from a non-main thread.
On most Windows machines this works, but it is technically not thread-safe and can cause
occasional flickering, crashes, or the icon update being silently dropped.

**Prevention:**
1. Post the icon update through `icon.update_menu()` or schedule it via Python's `threading.Event`
   rather than setting `icon.icon` directly from the callback thread.
2. Alternatively, use a `queue.Queue`: the monitoring thread puts `("color", "red")` messages
   into the queue, and the tray's `setup` function (which runs in its own thread per pystray's
   design) drains the queue and applies updates.
3. At minimum, add exception handling around icon-update calls in the monitoring callback so
   that a tray icon error never crashes the monitoring thread.

**Phase:** System tray phase + background polling integration.

---

### MODERATE — Ghost Tray Icon on Unclean Exit

**What goes wrong:** If the application exits without calling `icon.stop()`, the Win32 window
that backs the tray icon is destroyed but the system tray notification area on the Windows
taskbar retains the ghost icon until the user moves their mouse over it. This is a known Windows
behavior (the tray only repaints on mouse hover). Users see a stuck icon in the tray.

**Prevention:**
1. Call `icon.stop()` in the `finally` block in `cli/main.py`. The existing code already has a
   `finally: restore_terminal(...)` section — add `icon.stop()` immediately before or after
   `orchestrator.stop()`.
2. Register a signal handler for `SIGTERM` (on Windows: `signal.CTRL_C_EVENT` and
   `signal.CTRL_BREAK_EVENT`) that calls `icon.stop()` before exiting.
3. Handle the tray icon's own "Exit" menu item: `icon.stop()` must be called in the menu
   action, and `icon.stop()` must also signal the main loop to exit (e.g., by setting the
   same `_stop_event` that the orchestrator uses).

**Phase:** System tray phase. Cleanup path is as important as the happy path.

---

### MINOR — Pillow Dependency Adds 20–50 MB to the Install

**What goes wrong:** Pillow brings in JPEG/PNG/TIFF codec binaries. On a fresh venv, `pip install
pillow` adds approximately 20-50 MB. For a tool that generates its icon programmatically, this
is more than strictly necessary. This is not a functional pitfall but a dependency weight one.

**Prevention:** Accept the dependency. The alternatives (using a `.ico` file, using ctypes to
draw directly into an HICON, or using `wand`) are all more complex and more fragile. Pillow is
already a standard Pythonic image dependency and pystray documentation explicitly uses it in all
examples.

**Phase:** System tray phase. Note the dependency in the phase plan so it is not a surprise.

---

## Area 4: Background Polling Thread

### CRITICAL — Rich Live `update()` Called From a Background Thread Can Corrupt the Display

**What goes wrong:** The existing monitoring orchestrator calls `on_data_update` (registered in
`cli/main.py`) from inside `_monitoring_loop`, which runs in `_monitor_thread`. Inside
`on_data_update`, `live_display.update(renderable)` is called. Rich's `Live` class uses an
internal `RLock` (`_lock`) to serialize renders. Calling `update()` from a non-main thread is
the documented thread-safe usage pattern for Rich. However, there is a confirmed bug
(Textualize/rich#1530) where concurrent `console.print()` calls and `Live` updates from
different threads can produce garbled output — lines interleaved, escape sequences incomplete.

**Why it happens:** The existing code already does this (v1.0 works this way), so this is an
existing pattern. The v2.0 risk is that the web fetch thread adds a third thread (`_monitor_thread`
+ potential `_web_fetch_thread`) calling `update()` approximately simultaneously. Double-update
at near the same time can overflow the render lock acquisition.

**Prevention:**
1. Keep exactly one thread responsible for calling `live_display.update()`. The monitoring
   orchestrator's callback is already that thread. Do not create a separate web-fetch thread
   that also calls `update()`.
2. Merge the web fetch result into the monitoring data dict inside `_fetch_and_process_data()`
   before the single `on_data_update()` callback fires. The web fetch should be a synchronous
   call inside the monitoring loop, not a parallel thread.
3. If the web fetch is slow (Playwright startup, Cloudflare challenge), add a timeout
   (`requests` supports `timeout=10`, Playwright supports `page.goto(timeout=10000)`) so the
   monitoring loop never blocks indefinitely waiting for the web fetch.

**Phase:** Background polling + web fetch integration phase.

---

### CRITICAL — Unhandled Exception in the Monitoring Thread Silently Kills It

**What goes wrong:** The monitoring thread is a daemon thread (`daemon=True`, line 56 in
`orchestrator.py`). If `_monitoring_loop` raises an unhandled exception, the thread terminates
silently. `_monitoring: bool` stays `True`, `_monitor_thread.is_alive()` returns `False`, but
the UI continues to display the last rendered frame indefinitely. The user sees a frozen dashboard
that shows no error. This is the existing behavior for v1.0 and becomes more likely in v2.0
because the web fetch path introduces new failure modes (SQLite errors, HTTP errors, Cloudflare
blocks, JSON parse errors).

**Prevention:**
1. The existing `_fetch_and_process_data` already has a broad `except Exception as e` at its
   outer layer (line 227). Verify this covers all new web fetch code paths — do not leave any
   code outside this exception fence.
2. Add a watchdog: after `orchestrator.start()`, periodically check
   `orchestrator._monitor_thread.is_alive()`. If the thread has died, surface a UI error row
   ("Monitoring stopped — restart the app") instead of showing a frozen last-state dashboard.
3. Add exception logging in the web fetch code specifically. HTTP errors and JSON parse errors
   must be caught, logged, and converted to a `WebFetchResult(success=False, error="...")` value
   rather than raised as exceptions that reach the monitoring loop's outer handler.

**Phase:** Background polling phase. The watchdog should be added before v2.0 ships.

---

### MODERATE — Web Fetch Timeout Blocks the Monitoring Loop

**What goes wrong:** The monitoring loop calls `_fetch_and_process_data()` synchronously every
`update_interval` seconds. If the web fetch (Playwright startup + page render + data extraction)
takes 15–30 seconds, the entire monitoring loop stalls. No JSONL data is refreshed during this
time. The dashboard appears frozen. This is especially bad on first startup, when Playwright
launches a fresh browser instance.

**Prevention:**
1. Run the web fetch on a dedicated thread or use Python `concurrent.futures.ThreadPoolExecutor`
   with a `Future.result(timeout=15)` timeout so the monitoring loop can proceed with JSONL-only
   data if the web fetch takes too long.
2. Cache the last successful web result. On each monitoring loop iteration, use the cached value
   if it is fresh enough; only start a new web fetch when the cache is stale. This decouples web
   fetch latency from display update latency.
3. Design the web fetch as a "fire and forget, use result when available" operation: the
   monitoring loop publishes an update with whatever web data is currently available (even
   if stale), and the web fetch result is merged in asynchronously when it completes.

**Phase:** Web fetch + background polling integration phase.

---

### MODERATE — Graceful Shutdown Must Stop All Three Components in the Right Order

**What goes wrong:** v2.0 adds the tray icon as a third component alongside the monitoring
thread and Rich Live display. The existing `finally` block in `cli/main.py` stops the orchestrator
and exits the Live context. If the tray icon's event loop is not stopped before `sys.exit()`,
Win32 message pump teardown can race with Python's interpreter shutdown, producing an
`AttributeError: 'NoneType' object has no attribute ...` during garbage collection, or leaving
the ghost icon in the tray.

**Prevention:**
1. Shutdown order: `icon.stop()` → `orchestrator.stop()` → `live_display.__exit__()` →
   `restore_terminal()`. Stop the tray first because its Win32 message loop runs independently.
2. The tray icon's "Exit" menu item must trigger the same shutdown sequence as Ctrl+C. Use
   a `threading.Event` shared between the tray action and the main loop to signal "exit
   requested" without calling `sys.exit()` from inside the tray callback (which is unsafe in
   a message handler context).
3. Wrap every component's stop call in `contextlib.suppress(Exception)` (the existing code
   already does this for the Live display). Extend the same pattern to `icon.stop()`.

**Phase:** System tray + shutdown integration phase.

---

## Area 5: Hybrid Data Merging

### CRITICAL — Web Totals and JSONL Totals Will Diverge; No Clear Tie-Breaking Rule

**What goes wrong:** The claude.ai web API reports authoritative usage totals. The local JSONL
logs provide per-project breakdown but are approximations due to streaming deduplication
complexity, costUSD field removal, and session boundary ambiguity. When both sources are present,
they will report different total token counts. Without a documented tie-breaking rule, the display
code will either show two conflicting numbers or silently pick one, leading to user confusion.

**Specific divergence sources:**
- Web total includes all platforms (Claude.ai web, Claude Code, API); JSONL only has Claude Code
  local sessions
- JSONL deduplication may miss edge cases the web API handles server-side
- Clock skew between when a session ends and when the web API reflects it (likely eventual
  consistency)

**Prevention:**
1. Define the authoritative source for each data type before writing any merge code:
   - Plan limits (tokens/month): web only (JSONL has no plan limit data)
   - Aggregate usage total: web only (authoritative billing source)
   - Per-project breakdown: JSONL only (web does not provide this)
   - INCLUDED/OVERAGE status: derived from web totals against web plan limit
2. The hybrid merge should not "blend" totals — it should use each source for the data type
   it exclusively owns. There is no valid reason to average or sum across both sources.
3. If the web fetch fails, display the JSONL total with an explicit "(estimated — web data
   unavailable)" annotation. Do not silently substitute one for the other without labeling it.
4. Log any large divergence (>10%) between web total and JSONL total at WARNING level to aid
   future debugging.

**Phase:** Hybrid data layer phase. This architectural rule must be documented as a decision in
`STATE.md` before the merge code is written.

---

### MODERATE — Web Fetch Failure Must Degrade Gracefully, Not Crash the Dashboard

**What goes wrong:** The existing dashboard was built on JSONL-only data. In v2.0, if web fetch
is absent (Cloudflare blocked, session expired, Playwright not installed), the dashboard must
still function. If any v2.0 display code assumes `web_data is not None`, a `None` dereference
will crash the display update callback, leaving the dashboard frozen on the last rendered frame.

**Prevention:**
1. Design the `WebFetchResult` as an explicit optional: either a `WebFetchResult(success=True,
   plan_limit=..., total_tokens=...)` or a `WebFetchResult(success=False, error="...",
   plan_limit=None, total_tokens=None)`.
2. All display code that consumes web data must handle the `success=False` case explicitly. Use
   Python's `Optional` type hints throughout and treat `None` web fields as "show JSONL estimate
   with disclaimer" rather than "crash".
3. Add a unit test that simulates a `WebFetchResult(success=False)` and asserts the dashboard
   renders without error.

**Phase:** Hybrid data layer phase and display update phase.

---

### MINOR — Web Total Is Monthly; JSONL Is Session-Window-Based

**What goes wrong:** The existing v1.0 dashboard is built around 5-hour rolling session windows.
The claude.ai usage API (if it exposes what the settings page shows) is likely monthly billing
totals. Mixing these two time granularities in the same display row creates confusion: "You've
used 120,000 tokens (monthly total) out of 500,000 (monthly plan limit)" displayed next to
"Current session: 45,000 tokens" is coherent, but the code must never divide one by the other
or compare them directly.

**Prevention:**
1. Use separate variables for monthly totals (from web) and session totals (from JSONL).
   Never add them together.
2. The pool-spend display (v1.0 feature) was built on session-window logic. In v2.0, replace or
   supplement that calculation with the monthly total from the web API if available.
3. Add comments to any code that performs a calculation involving tokens, noting explicitly
   whether the token count is session-scoped or monthly-scoped.

**Phase:** Hybrid data layer phase. Document in code via type annotations or explicit variable
naming (`monthly_tokens_used` vs `session_tokens_used`).

---

## Area 6: Monthly Reset on the 1st

### MODERATE — Timezone of the Monthly Reset Is Unknown and Machine-Dependent

**What goes wrong:** Anthropic's billing cycle likely resets at midnight on the 1st in a
specific timezone (most likely UTC or US/Pacific). The user's machine may be in a different
timezone. If the code uses `datetime.now().day == 1` to detect the reset, it triggers the reset
at local midnight on the 1st, which may be hours before or after Anthropic's actual reset.
During this gap, the JSONL-based pool spend and the web-reported total will diverge in a way
that looks like a bug.

**Prevention:**
1. Use UTC for all monthly reset calculations internally. `datetime.now(timezone.utc).day == 1`
   is the correct form. Never use naive `datetime.now().day`.
2. Make the reset timezone configurable (add `billing_reset_timezone: "UTC"` to config.json
   with UTC as default). If the user knows their plan resets in US/Pacific, they can set it.
3. The pool_spend persistence (the existing `pool_spend.json` cache from v1.0) already has a
   `billing_period_start` field. Verify that the reset logic uses this field rather than
   recomputing from `datetime.now()` on every startup, which would cause incorrect resets if
   the tool is started on the 1st but after Anthropic has already reset.

**Phase:** Monthly reset phase. This is a subtle edge case that is invisible until the 1st of
the month.

---

### MODERATE — "Last Day of the Month" Edge Cases

**What goes wrong:** February has 28 or 29 days. Months have 28, 30, or 31 days. Code that
assumes "the current billing period started on `billing_start_day` of this month" will fail when
`billing_start_day = 29`, `30`, or `31` and the current month has fewer days. The calculation
`datetime(current_year, current_month, billing_start_day)` will raise `ValueError: day is out of
range for month`.

**Prevention:**
1. Use `min(billing_start_day, calendar.monthrange(year, month)[1])` when constructing the
   billing period start date.
2. Write unit tests for February with billing start day 30 and 31.
3. The existing `pool_state_manager.py` likely already handles this; verify it does before
   adding any new monthly-reset code that duplicates the billing period calculation.

**Phase:** Monthly reset phase. Check existing `pool_state_manager.py` first.

---

### MINOR — Midnight Reset Creates a Double-Count Window

**What goes wrong:** At exactly midnight on the 1st (in the reset timezone), the billing period
flips from month N to month N+1. If the monitoring loop fires at 11:59 PM and again at 12:01 AM,
the pool spend may accumulate in the old period's cache for the 11:59 run and then reset to zero
for the 12:01 run. If both runs happen before the UI refreshes, the user sees the pool spend jump
from some value to zero without the intermediate reset being visible.

**Prevention:** This is cosmetic — the data is correct. Accept it and document it. The reset is
correct; the visual discontinuity is a display artifact of the 5-minute polling interval.

**Phase:** Not a blocker. Document as known behavior.

---

## Phase-Specific Warning Summary

| Phase Topic | Highest-Risk Pitfall | Mitigation |
|-------------|----------------------|------------|
| Cookie extraction | Chrome v127+ ABE breaks simple DPAPI | Use browser-cookie3 v0.19.1+; Firefox fallback |
| Cookie extraction | SQLite lock while Chrome open | URI read-only + immutable=1 |
| Web fetch | claude.ai is SPA; requests returns empty HTML | Discover JSON API via DevTools first |
| Web fetch | Cloudflare blocks headless Python | Use curl_cffi with browser TLS impersonation |
| Web fetch | Undocumented API schema can change | Wrap all parsing in .get() with fallbacks |
| Web fetch | Session expiry returns 401 | Re-extract on auth failure; show UI indicator |
| System tray | pystray run() blocks main thread | Use run_detached(); never run() on main thread |
| System tray | Ghost icon on unclean exit | Call icon.stop() in finally block |
| System tray | Tray icon update from wrong thread | Post updates via queue, not direct assignment |
| Background polling | Web fetch blocks monitoring loop | Cache web result; use timeout on fetch |
| Background polling | Unhandled exception kills thread silently | Outer except already exists; extend to web paths |
| Background polling | Three-component shutdown ordering | icon.stop() → orchestrator.stop() → live.__exit__ |
| Hybrid data | JSONL and web totals diverge | Define authoritative source per data type upfront |
| Hybrid data | Web failure crashes display | Explicit WebFetchResult optional type; test None case |
| Monthly reset | Reset timezone mismatch | UTC internally; configurable in config.json |
| Monthly reset | billing_start_day > 28 in short months | calendar.monthrange() clamp |

---

## Confidence Levels

| Area | Confidence | Basis |
|------|------------|-------|
| Chrome v127 app-bound encryption | HIGH | Multiple security research sources; confirmed Chrome v127 Jul 2024; RedCanary analysis |
| SQLite lock while Chrome open | HIGH | Confirmed pycookiecheat issue #29 + SQLite forum; read-only URI mode documented |
| claude.ai is SPA | HIGH | React SPA is visible from page source; confirmed by Cloudflare issue #39896 in claude-code repo |
| Cloudflare blocking | HIGH | Confirmed in anthropics/claude-code#39896 (WebFetch fails on claude.ai) |
| pystray run() blocking + run_detached() | HIGH | pystray official docs 0.19.5 explicitly state this |
| Rich Live thread safety | MEDIUM | Confirmed issue Textualize/rich#1530; mitigations are documented workarounds |
| Web API schema stability | MEDIUM | Inferred from general internal-API risk; no specific incident documented |
| Cookie staleness | MEDIUM | Standard browser behavior; no claude.ai-specific incident documented |
| Monthly reset timezone | MEDIUM | Standard billing practice; Anthropic's specific reset timezone not publicly documented |
| Ghost tray icon | MEDIUM | pystray issue #94 and #17 discuss shutdown; Windows behavior is well-known |

---

## Sources

- [Chrome App-Bound Encryption Analysis — RedCanary](https://redcanary.com/blog/threat-intelligence/google-chrome-app-bound-encryption/)
- [Chrome-App-Bound-Encryption-Decryption (research)](https://github.com/xaitax/Chrome-App-Bound-Encryption-Decryption)
- [pycookiecheat: database is locked issue #29](https://github.com/n8henrie/pycookiecheat/issues/29)
- [Python Tutorials: Safely Open Locked SQLite Database](https://www.pythontutorials.net/blog/is-it-possible-to-open-a-locked-sqlite-database-in-read-only-mode/)
- [WebFetch fails on claude.ai — Cloudflare blocks headless (anthropics/claude-code#39896)](https://github.com/anthropics/claude-code/issues/39896)
- [pystray docs: Creating a system tray icon (0.19.5)](https://pystray.readthedocs.io/en/latest/usage.html)
- [pystray: Icon.stop() threading issue #94](https://github.com/moses-palmer/pystray/issues/94)
- [pystray: terminate from tray menu #17](https://github.com/moses-palmer/pystray/issues/17)
- [Rich: Live display not thread safe #1530](https://github.com/willmcgugan/rich/issues/1530)
- [Rich: Console not terminal in background thread #2665](https://github.com/Textualize/rich/issues/2665)
- [Anthropic Privacy: What Cookies Does Anthropic Use?](https://privacy.claude.com/en/articles/10023541-what-cookies-does-anthropic-use)
- [Decrypt Chrome v20 cookies with appbound protection (gist)](https://gist.github.com/thewh1teagle/d0bbc6bc678812e39cba74e1d407e5c7)
- [How to Stop a Python Thread Cleanly — Alexandra Zaharia](https://alexandra-zaharia.github.io/posts/how-to-stop-a-python-thread-cleanly/)
