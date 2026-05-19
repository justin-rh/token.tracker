---
phase: 06-per-project-breakdown
verified: 2026-05-19T21:55:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run dashboard with --plan custom and confirm per-project columns render correctly"
    expected: "Side-by-side Today (est.) / This month (est.) columns appear between pool section and web section; D-07 rows absent; D-08 rows after Last web sync"
    why_human: "Visual layout verification — smoke-test was approved per 06-04-SUMMARY.md (Task 2 checkpoint) but cannot be re-verified programmatically; re-confirm if layout changes are suspected"
---

# Phase 6: Per-Project Breakdown Verification Report

**Phase Goal:** Users can see which Claude Code project folders consumed the most tokens today and this billing month, giving context for where usage is coming from
**Verified:** 2026-05-19T21:55:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Dashboard shows ranked list of project folders by token count for UTC calendar day, labeled "est." — sourced from JSONL | VERIFIED | `ui/session_display.py` line 330: `"📂 [value]Today (est.)[/]"` header; live run produces 5 real entries (e.g. `[('rhoda', 44483720), ('subagents', 37649319), ...]`) |
| 2 | Dashboard shows ranked list of project folders by token count for billing month, labeled "est." — sourced from JSONL | VERIFIED | `ui/session_display.py` line 331: `"📂 [value]This month (est.)[/]"` header; live run produces 3 real entries from JSONL |
| 3 | Per-project token figures unchanged when web data available — never overwrites, augments, or mixes with JSONL rows | VERIFIED | `project_breakdown = compute_project_breakdown()` (orchestrator line 207) runs unconditionally from JSONL; the per-project block in session_display is separate from the `if web_usage is not None:` block; no web data path touches project_breakdown |
| 4 | ProjectBreakdown frozen dataclass exists and is importable from core/models.py | VERIFIED | `python -c "from claude_monitor.core.models import ProjectBreakdown; pb = ProjectBreakdown(today=[('tok', 100)], billing_month=[], as_of=datetime.now(timezone.utc)); print('OK:', pb)"` → OK; `frozen=True` confirmed; `FrozenInstanceError` raised on assignment attempt |
| 5 | core/project_breakdown.py exports compute_project_breakdown() with JSONL scanning | VERIFIED | `python -c "from claude_monitor.core.project_breakdown import compute_project_breakdown; print('OK')"` → OK; live call returns real data |
| 6 | Deduplication by requestId applied — token counts not 100-174x inflated | VERIFIED | `_deduplicate_entries` imported from `claude_monitor.data.reader` (line 25); called at line 166; not reimplemented (`grep "def _deduplicate_entries" core/project_breakdown.py` → 0 matches); 7 unit tests including deduplication test all pass |
| 7 | compute_project_breakdown() called in orchestrator every cycle; monitoring_data["project_breakdown"] key always present | VERIFIED | `monitoring/orchestrator.py` line 207: `project_breakdown = compute_project_breakdown()`; line 215: `"project_breakdown": project_breakdown,  # Phase 6 NEW`; import at line 11 confirmed |
| 8 | project_breakdown wired through display_controller and cli/main.py to session_display | VERIFIED | `display_controller.py` line 211: `project_breakdown: Optional[Any] = None, # Phase 6 NEW`; line 291: `processed_data["project_breakdown"] = project_breakdown`; `cli/main.py` line 234: `project_breakdown=monitoring_data.get("project_breakdown"), # Phase 6 NEW` |
| 9 | D-07 rows (Cost Usage, Token Usage, Messages Usage, Time to Reset) absent from custom/pro/max5/max20 branch | VERIFIED | grep confirms "Token Usage" at lines 410, 532 (else branch and format_no_active_session_screen only); "Time to Reset" at line 435 (else branch only); "Cost Usage" and "Messages Usage" — 0 matches anywhere |
| 10 | D-08 rows (Model Distribution, Burn Rate, Cost Rate) inside `if web_usage is not None:` block; else branch unchanged with Session Cost still present | VERIFIED | Model Distribution at lines 375/378, Burn Rate at line 383, Cost Rate at line 392 — all inside web_usage block (lines 346-394); "Session Cost" at line 403 (else branch, D-10 confirmed) |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `core/models.py` | ProjectBreakdown frozen dataclass | VERIFIED | Lines 134-150; `frozen=True`, `today: list[tuple[str, int]]`, `billing_month: list[tuple[str, int]]`, `as_of: datetime`; no new imports added |
| `core/project_breakdown.py` | compute_project_breakdown() factory | VERIFIED | 204 lines; exports `compute_project_breakdown`; imports `_deduplicate_entries`; `encoding="utf-8-sig"` at line 146; `PermissionError` handled at line 156; display name `split("-")[-1]` at line 142 |
| `tests/test_project_breakdown.py` | 7 unit tests | VERIFIED | All 7 pass: `pytest tests/test_project_breakdown.py -v` → 7 passed |
| `monitoring/orchestrator.py` | project_breakdown in monitoring_data every cycle | VERIFIED | Import line 11, call line 207, dict key line 215 |
| `ui/session_display.py` | Per-project columns + D-07 removed + D-08 relocated | VERIFIED | `_fmt_tokens` (line 31), `_col_pad` (line 40), project_breakdown guard (line 327-342), D-08 inside web_usage block (lines 372-394) |
| `ui/display_controller.py` | project_breakdown kwarg accepted and threaded through | VERIFIED | Parameter line 211, threaded through at line 291 |
| `cli/main.py` | project_breakdown extracted from monitoring_data and passed to display | VERIFIED | Line 234 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `core/models.py` | `core/project_breakdown.py` | `from claude_monitor.core.models import ProjectBreakdown` | WIRED | Line 24 of project_breakdown.py |
| `core/project_breakdown.py` | `claude_monitor.data.reader._deduplicate_entries` | `from claude_monitor.data.reader import _deduplicate_entries` | WIRED | Line 25; called at line 166 |
| `monitoring/orchestrator.py` | `core/project_breakdown.py` | `from claude_monitor.core.project_breakdown import compute_project_breakdown` | WIRED | Import line 11; call line 207; result placed in monitoring_data line 215 |
| `monitoring/orchestrator.py` | `ui/session_display.py` (via display_controller) | `monitoring_data["project_breakdown"]` → `display_controller.create_data_display(project_breakdown=...)` | WIRED | cli/main.py line 234 extracts from monitoring_data; display_controller line 291 threads into processed_data |
| `ui/session_display.py` | `monitoring_data["project_breakdown"]` | `project_breakdown = kwargs.get("project_breakdown")` | WIRED | Line 327; guard line 328 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `ui/session_display.py` per-project section | `project_breakdown.today`, `project_breakdown.billing_month` | `compute_project_breakdown()` → JSONL rglob scan → `_deduplicate_entries` → token accumulation | Yes — live run returned `[('rhoda', 44483720), ('subagents', 37649319), ('report', 7501167), ('bts', 2584851), ('tracker', 2218919)]` | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| compute_project_breakdown() returns real JSONL data | `python -c "from claude_monitor.core.project_breakdown import compute_project_breakdown; pb = compute_project_breakdown(); print(len(pb.today), len(pb.billing_month))"` | `5 3` | PASS |
| ProjectBreakdown importable and constructable | `python -c "from claude_monitor.core.models import ProjectBreakdown; ..."` | `OK: ProjectBreakdown(...)` | PASS |
| Orchestrator imports cleanly | `python -c "from claude_monitor.monitoring.orchestrator import MonitoringOrchestrator; print('OK')"` | `OK` | PASS |
| SessionDisplayComponent imports cleanly | `python -c "from claude_monitor.ui.session_display import SessionDisplayComponent; print('OK')"` | `OK` | PASS |
| All 7 unit tests pass | `python -m pytest tests/test_project_breakdown.py -v` | `7 passed` | PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| PROJ-01 | 06-01, 06-02, 06-03, 06-04 | Terminal dashboard shows which project folders consumed most tokens today (UTC), sourced from JSONL with "est." prefix | SATISFIED | `"📂 [value]Today (est.)[/]"` header in session_display.py; live data confirms real project token counts from JSONL |
| PROJ-02 | 06-01, 06-02, 06-03, 06-04 | Terminal dashboard shows which project folders consumed most tokens this billing month, sourced from JSONL with "est." prefix | SATISFIED | `"📂 [value]This month (est.)[/]"` header in session_display.py; billing_start derived from config billing_cycle_start_day; live data confirms real billing-month data |
| PROJ-03 | 06-01, 06-02, 06-03, 06-04 | Per-project token data sourced exclusively from local JSONL, never merged with or replaced by web data | SATISFIED | `compute_project_breakdown()` scans JSONL only; no web data code path touches project_breakdown; the per-project display block is independent of the `if web_usage is not None:` block |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No stubs, placeholders, or hollow implementations found |

**Notes on deviation found:**
- `_DEFAULT_DATA_PATH` in `core/project_breakdown.py` uses `Path.home() / ".claude" / "projects"` rather than `Path(os.environ["APPDATA"]) / ".claude" / "projects"` as shown in the plan's interface block. This is **correct per CLAUDE.md**: "Use `Path.home() / '.claude' / 'projects'`". Verified `Path.home() / ".claude" / "projects"` resolves to `C:\Users\justin.rhoda\.claude\projects` and EXISTS. The APPDATA path (`C:\Users\justin.rhoda\AppData\Roaming\.claude\projects`) does NOT exist. This deviation is intentional and correct.
- ROADMAP.md still marks `06-04-PLAN.md` as `- [ ]` (unchecked). This is a documentation gap — the code is fully implemented and working. Does not affect functionality.

### Human Verification Required

#### 1. Visual layout smoke-test

**Test:** Run `python monitor.py --plan custom`, wait 15 seconds for first monitoring cycle + web sync to complete
**Expected:**
- Side-by-side project columns appear between pool section and web section
- Left header: "📂 Today (est.)", Right header: "📂 This month (est.)"
- At least one project row visible with token count (e.g. "rhoda   44.5M tok")
- D-07 rows absent: no "💰 Cost Usage", "📊 Token Usage", "📨 Messages Usage", "⏱️ Time to Reset" in the custom branch
- D-08 rows present after "Last web sync": Model Distribution, Burn Rate, Cost Rate
- No crash, no traceback, no blank/empty rows where content is expected
**Why human:** Visual terminal layout cannot be verified programmatically; smoke-test was previously approved per 06-04-SUMMARY.md Task 2 checkpoint. Re-confirm if code has changed since approval.

### Gaps Summary

No gaps found. All 10 observable truths are verified. All artifacts exist, are substantive, and are wired. Data flows from JSONL through the full stack and the live `compute_project_breakdown()` call returns real ranked project data.

The only open item is the human visual smoke-test, which was previously approved but is categorized as `human_needed` per verifier protocol (visual layout verification requires human confirmation).

---

_Verified: 2026-05-19T21:55:00Z_
_Verifier: Claude (gsd-verifier)_
