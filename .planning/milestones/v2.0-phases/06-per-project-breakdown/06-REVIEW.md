---
phase: 06-per-project-breakdown
reviewed: 2026-05-19T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - core/models.py
  - core/project_breakdown.py
  - tests/test_project_breakdown.py
  - monitoring/orchestrator.py
  - ui/session_display.py
  - ui/display_controller.py
  - cli/main.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-19
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 6 adds `ProjectBreakdown` (frozen dataclass), `compute_project_breakdown()`, wiring through the orchestrator and display stack, and side-by-side column rendering in the terminal dashboard. The architecture is sound and the key design decisions (deduplication reuse, `utf-8-sig`, per-file `PermissionError` catch, `_col_pad` helper, `_fmt_tokens` tiers) are all correctly implemented.

Four warnings and four info items were found. No critical security or data-loss issues exist. The most impactful warning is a logic gap in Test 4 (billing-month filter) that can produce a false pass on certain days of the month. The second-most impactful is a display-name collision: multiple projects that share the same last segment (e.g. two repos both named `tracker`) will silently merge their token counts — by design per D-01, but currently undocumented and untested.

---

## Warnings

### WR-01: Test 4 billing-month filter has a fragile day-of-month assumption

**File:** `tests/test_project_breakdown.py:165`
**Issue:** Test 4 uses `_days_ago_str(5)` as the "within billing month" entry and assumes it is always inside the current billing period when `billing_cycle_start_day=1`. This is only true when `today.day >= 6`. On days 1–5 of the month the billing period has just rolled over; `5 days ago` falls in the *previous* billing month. When that happens `month_dict["delta"]` will be 0 and the assertion on line 180 (`assert month_dict["delta"] == 300`) will fail.

**Fix:** Derive the in-billing timestamp from the computed `billing_start` directly rather than from a fixed offset:
```python
from core.project_breakdown import _derive_billing_cycle_start, _read_cycle_day

billing_start = _derive_billing_cycle_start(1)
# Use a date that is guaranteed within the current period
in_billing_ts = datetime(billing_start.year, billing_start.month, billing_start.day,
                         12, 0, 0, tzinfo=timezone.utc)
in_billing = in_billing_ts.isoformat()
```
Alternatively, anchor the test with a mocked `date.today()` (via `unittest.mock.patch`).

---

### WR-02: Display-name key collision silently merges unrelated projects

**File:** `core/project_breakdown.py:143`
**Issue:** `display_name = slug.split("-")[-1]` is intentional (D-01), but when two separate project directories share the same last segment — e.g. `C:-Users-alice-token-tracker` and `C:-Users-bob-token-tracker` — their token counts accumulate into a single `"tracker"` key. The user sees inflated numbers for that project with no indication that multiple repos are merged. On a shared machine or when the same project is cloned under multiple paths this will silently misreport.

**Fix (short-term):** Document the known limitation in a comment adjacent to the assignment, and add a `logger.debug` that logs when a collision occurs:
```python
display_name = slug.split("-")[-1]
if display_name in today_tokens or display_name in month_tokens:
    logger.debug(
        "project_breakdown: display_name collision for '%s' (slug=%s) — "
        "tokens merged into existing key",
        display_name, slug,
    )
```
**Fix (longer-term):** Consider using the last two segments (`"-".join(slug.split("-")[-2:])`) to reduce collision probability without making names too verbose. Document the chosen policy in CLAUDE.md / project docs.

---

### WR-03: `_derive_billing_cycle_start` uses local date; `today_date` uses UTC — cross-midnight skew

**File:** `core/project_breakdown.py:135`
**Issue:** `today_date` is derived from `datetime.now(timezone.utc).date()` (UTC), but `_derive_billing_cycle_start` calls `date.today()` (local system clock). On a Windows machine in UTC+X when UTC has rolled past midnight but local time has not, `today_date` can be one day ahead of the date used to compute `billing_start`. This means an entry timestamped "today UTC" could be excluded from `billing_month` if the billing cycle just rolled at the local midnight. The discrepancy also means `today_date` and `billing_start` are computed in different timezones, which is inconsistent.

**Fix:** Pass `today` explicitly from the caller to `_derive_billing_cycle_start`, using the UTC date throughout:
```python
today_utc: date = datetime.now(timezone.utc).date()
billing_start = _derive_billing_cycle_start(cycle_day, today=today_utc)
today_date = today_utc
```
Update the helper signature:
```python
def _derive_billing_cycle_start(cycle_day: int, today: date | None = None) -> date:
    today = today or date.today()
    ...
```

---

### WR-04: `format_active_session_screen` project-breakdown rows use `{name:<22}` f-string width, not `_col_pad`

**File:** `ui/session_display.py:333-335`
**Issue:** The per-project row formatting uses a plain f-string field width (`{name:<22}`) inside the left-column string before it is passed to `_col_pad`. Because `name` is a plain ASCII string this works correctly *today*, but if a project name ever contains Rich markup tags or wide Unicode characters the inner `:<22` will measure Python string length (not terminal width) while the outer `_col_pad` measures terminal-visible width. The two measurements will diverge and produce misaligned columns. The `_col_pad` helper was introduced precisely to fix this class of bug; it should be applied at the innermost level.

**Fix:** Remove the `:<22` f-string width and delegate all padding to `_col_pad`:
```python
# Replace lines 333-334:
for name, toks in (project_breakdown.today or []):
    left_lines.append(f"  [dim]{_col_pad(name, 22)}[/] {_fmt_tokens(toks)}")
for name, toks in (project_breakdown.billing_month or []):
    right_lines.append(f"  [dim]{_col_pad(name, 22)}[/] {_fmt_tokens(toks)}")
```
Note: `_col_pad` must be applied *before* the Rich markup tags are added because it strips markup before measuring. The approach above applies it inside the `[dim]...[/]` tags, which is correct — the stripped version measures only `name`.

---

## Info

### IN-01: Test 6 docstring asserts display name is `"token-tracker"` but implementation yields `"tracker"`

**File:** `tests/test_project_breakdown.py:221`
**Issue:** The docstring on line 221 says `Display name for slug 'C:-Users-justin-rhoda-token-tracker' → 'token-tracker'`, but `slug.split("-")[-1]` returns `"tracker"`, not `"token-tracker"`. The assertion on line 233 correctly checks for `"tracker"`, so the test passes, but the docstring is misleading and will confuse future maintainers.

**Fix:** Correct the docstring:
```python
"""Display name for slug 'C:-Users-justin-rhoda-token-tracker' → 'tracker' (last segment)."""
```

---

### IN-02: `compute_project_breakdown()` called with no arguments in orchestrator — ignores `data_path`

**File:** `monitoring/orchestrator.py:207`
**Issue:** `compute_project_breakdown()` is called with no arguments at line 207, so it always falls back to `Path.home() / ".claude" / "projects"`. The orchestrator already holds a `data_path` from its constructor (`self.data_manager` is initialized with it), but that path is never forwarded to `compute_project_breakdown`. On a machine where data lives elsewhere (non-standard install or test environment) the project breakdown will always be empty while all other displays use the correct path.

**Fix:** Pass the orchestrator's data path through:
```python
# In MonitoringOrchestrator.__init__, store data_path:
self._data_path: Optional[Path] = Path(data_path) if data_path else None

# In _fetch_and_process_data:
project_breakdown = compute_project_breakdown(
    data_path=self._data_path,
)
```

---

### IN-03: Commented-out debug-style `logger.exception` calls in display_controller.py

**File:** `ui/display_controller.py:301-318`
**Issue:** The exception handler in `create_data_display` uses `logger.exception(...)` (which logs at ERROR level with traceback) for per-key diagnostic dumps of `processed_data`. This is appropriate during development but will produce very verbose ERROR-level output in production when any display formatting error occurs. `logger.debug` would be more appropriate for the per-key dump.

**Fix:** Change the diagnostic key-dump lines to `logger.debug`:
```python
logger.debug(f"processed_data type: {type(processed_data)}")
# ... and the inner per-key lines ...
logger.debug(f"  {key}: {type(value).__name__} = {value}")
```
Keep `logger.error` for the top-level `"Error in format_active_session_screen: {e}"` line.

---

### IN-04: `_col_pad` strips all `[...]` bracket sequences, including Rich color codes with colons

**File:** `ui/session_display.py:47`
**Issue:** The regex `r'\[/?[^\]]*\]'` strips any sequence matching `[anything]`. This is correct for Rich markup like `[bold]`, `[dim]`, `[/]`, and `[value]`. However, if a project name itself contains square brackets (e.g. a directory named `my-project[v2]`) the regex will silently strip the bracketed portion when computing visible width, causing the padding to be slightly too wide. This is a low-probability edge case but worth noting.

**Fix:** No immediate action required — project slug characters are constrained to filesystem-safe characters. Add a comment explaining the assumption:
```python
# NOTE: Rich markup stripped via regex. Assumes project names (display_name)
# contain no literal square brackets — filesystem slugs on Windows/macOS/Linux
# do not allow '[' or ']' in directory names.
stripped = _re.sub(r'\[/?[^\]]*\]', '', s)
```

---

_Reviewed: 2026-05-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
