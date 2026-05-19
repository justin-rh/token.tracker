# Phase 6: Per-Project Breakdown - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Surface which Claude Code project folders consumed the most tokens today (UTC calendar day) and this billing month, sourced exclusively from local JSONL files. Display as side-by-side columns in the terminal dashboard. Simultaneously restructure the existing dashboard layout by removing redundant rows and repositioning others.

Web data never overwrites, augments, or mixes with per-project JSONL figures (PROJ-03).

</domain>

<decisions>
## Implementation Decisions

### Project Name Display
- **D-01:** Display only the last path segment of the project folder slug. The `.claude/projects/` directories use Windows path-as-slug naming (e.g. `C:-Users-justin-rhoda-token-tracker`). Split on `-` and take the last meaningful segment → `token-tracker`. No full path shown.
- **D-02:** If two projects share the same last segment, show them as-is (no disambiguation needed for Phase 6 — rare case, acceptable collision).

### Token Counting
- **D-03:** Rank and display by **total tokens** = `input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens`. This matches the existing `TokenCounts.total_tokens` property — no new math. Accurately represents full API cost footprint per project.

### Row Count / Depth
- **D-04:** Show **top 5 projects** per list (today and billing month). No config option needed — fixed at 5 for Phase 6.

### Dashboard Placement
- **D-05:** Per-project section appears as **side-by-side columns** (today / billing month) in the terminal dashboard, positioned **below the Pool Spent section** and above the Web data section. The two lists share the same separator block and are horizontally divided.

- **D-06:** Column format (approximate — exact width Claude's discretion):
  ```
  ─────────────────────────────────────────────────────────────
  📂 Today (est.)            📂 This month (est.)
    token-tracker  88,420 tok   token-tracker  412,000 tok
    gstack         54,210 tok   gstack         198,100 tok
    claude-code-stack 12,800    some-other        4,100 tok
    some-other      4,100 tok   another-proj      1,200 tok
    another-proj    1,200 tok   misc-tools          800 tok
  ```
  Both lists use `est.` label in the section header (not per-row) per DISP-02.

### Dashboard Layout Restructure (same phase as project breakdown)
- **D-07: Remove these rows** from the `custom`/`pro`/`max5`/`max20` display branch:
  - `💰 Cost Usage` (progress bar)
  - `📊 Token Usage` (progress bar)
  - `📨 Messages Usage` (progress bar)
  - `⏱️ Time to Reset` (progress bar)

- **D-08: Move these rows** to below the `Last web sync` line (after Phase 4 web data rows):
  - `🤖 Model Distribution`
  - `🔥 Burn Rate`
  - `💲 Cost Rate`

- **D-09: New layout order** for `custom`/`pro`/`max5`/`max20` plan branch:
  ```
  Header (plan, timezone)
  [custom only: "Session-Based Dynamic Limits" header]
  ─────────────────────────────────────────────────────────────
  [Phase 2 threshold rows: Token limit + INCLUDED/OVERAGE status]
  ─────────────────────────────────────────────────────────────
  [Phase 3: Pool spent + progress bar + pool burn if OVERAGE]
  ─────────────────────────────────────────────────────────────
  [Phase 6: Per-project side-by-side columns (today / billing month)]
  ─────────────────────────────────────────────────────────────
  [Phase 4: Utilization + Resets in + Last web sync]
  🤖 Model Distribution   ← moved here
  🔥 Burn Rate            ← moved here
  💲 Cost Rate            ← moved here
  ─────────────────────────────────────────────────────────────
  [Predictions: Tokens will run out + Limit resets at]
  [Notifications]
  [Footer]
  ```

- **D-10:** The non-custom plan branch (else: branch in `format_active_session_screen`) is **not touched** in this phase — the user is on a custom plan and the else branch is out of scope.

### Data Pipeline
- **D-11:** New frozen dataclass `ProjectBreakdown` in `core/models.py` (follows ThresholdState / PoolState / WebUsageData pattern):
  ```python
  @dataclass(frozen=True)
  class ProjectBreakdown:
      today: list[tuple[str, int]]        # [(display_name, total_tokens), ...] top 5, UTC today
      billing_month: list[tuple[str, int]] # [(display_name, total_tokens), ...] top 5, billing month
      as_of: datetime                      # UTC timestamp when computed
  ```

- **D-12:** New function `compute_project_breakdown(data_path, billing_cycle_start_day) -> ProjectBreakdown` in a new module `core/project_breakdown.py`. Reads JSONL files directly (not through `load_usage_entries`) — scans by parent directory to group tokens per project slug. Extracts last path segment for display name. Deduplication by requestId MUST be applied (same strategy as `_deduplicate_entries` in `data/reader.py`).

- **D-13:** `compute_project_breakdown()` is called from `monitoring/orchestrator.py` inside `_fetch_and_process_data()`, alongside `compute_pool_state()`. Result added to `monitoring_data` dict as `"project_breakdown"` key.

- **D-14:** `session_display.py` receives `project_breakdown: Optional[ProjectBreakdown]` via `kwargs.get("project_breakdown")`. Only rendered if not None and at least one project exists in either list.

- **D-15:** Billing month scope: use `billing_cycle_start_day` from config (same key used by `pool_state_manager.py`). "This billing month" = entries on or after the most recent occurrence of that calendar day in UTC.

- **D-16:** "Today" scope: entries where `timestamp.date() == datetime.now(UTC).date()` (UTC calendar day, per PROJ-01).

### Claude's Discretion
- Exact column widths, padding, and alignment for the side-by-side layout
- Whether to show a `(N more)` indicator if there are more than 5 projects
- Handling of zero-token projects (exclude from list)
- Whether `compute_project_breakdown` is called every monitoring cycle (10s) or on a longer interval to avoid redundant JSONL re-reads

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 6 Requirements
- `.planning/REQUIREMENTS.md` — PROJ-01, PROJ-02, PROJ-03 are the full scope. Read for exact acceptance criteria.

### Prior Phase Context
- `.planning/phases/04-web-data-foundation/04-CONTEXT.md` — D-16 through D-20: web data display rows (Utilization, Resets in, Last web sync). Phase 6 adds rows AFTER Last web sync (Model Dist, Burn Rate, Cost Rate move here).
- `.planning/phases/03-overage-pool-dashboard/03-CONTEXT.md` — Pool section display pattern. Phase 6 per-project columns appear below this section.
- `.planning/phases/02-threshold-detection/02-CONTEXT.md` — Threshold rows that remain in the layout (not removed by this phase).

### Source Files (Key Integration Points)
- `ui/session_display.py` — `format_active_session_screen()`: layout restructure (D-07, D-08, D-09); add per-project rendering (D-14). Read the full function before editing.
- `data/reader.py` — `_find_jsonl_files()`, `_deduplicate_entries()`: these must be reused in `core/project_breakdown.py` — do NOT duplicate the deduplication logic.
- `core/models.py` — Add `ProjectBreakdown` frozen dataclass (D-11).
- `monitoring/orchestrator.py` — Add `project_breakdown` key to `monitoring_data` (D-13).
- `core/pool_state_manager.py` — Read to understand how `billing_cycle_start_day` is accessed from config — replicate the same config read pattern in `compute_project_breakdown()` (D-15).
- `.planning/STATE.md` — Architecture notes: threading model, established module extension list.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `data/reader.py:_find_jsonl_files(data_path)` — returns `list[Path]` from `data_path.rglob("*.jsonl")`. Use this directly; `file_path.parent.name` gives the project slug.
- `data/reader.py:_deduplicate_entries(entries)` — requestId deduplication (max output_tokens strategy). MUST reuse in project breakdown to avoid 100-174x inflation.
- `core/pool_state_manager.py:compute_pool_state()` — reference for config read pattern (`billing_cycle_start_day`) and frozen dataclass + factory function convention.
- `core/models.py` — `TokenCounts.total_tokens` property; `WebUsageData` frozen dataclass — follow the same pattern for `ProjectBreakdown`.
- `ui/session_display.py:_render_wide_progress_bar()` — not needed for project rows, but the established Rich markup style should be followed for consistency.

### Established Patterns
- `monitoring_data` dict: new state keys added here, passed as `kwargs` to `session_display.py`
- Frozen dataclass + factory function for new state objects (ThresholdState, PoolState, WebUsageData)
- All JSONL-derived figures labeled "est." — per DISP-02 (in section header, not per row)
- `kwargs.get("key")` pattern in `format_active_session_screen` for optional state

### Integration Points
- `monitoring/orchestrator.py:_fetch_and_process_data()` — add `"project_breakdown": compute_project_breakdown(...)` to `monitoring_data` dict alongside pool_state
- `ui/session_display.py:format_active_session_screen()` — add `project_breakdown` rendering in D-09 position; remove D-07 rows; move D-08 rows

</code_context>

<specifics>
## Specific Ideas

- Section header format: `📂 Today (est.)` and `📂 This month (est.)` as column headers, side by side
- Token display: abbreviated with `k` suffix for thousands (e.g. `88,420 tok` or `88.4k tok`) — Claude's discretion on threshold
- Separator: standard `[separator]{'─' * 60}[/]` consistent with all other section separators
- The two per-project lists share one separator block — they don't get their own top and bottom separators independently

</specifics>

<deferred>
## Deferred Ideas

- Configurable row count (`project_breakdown_rows` config key) — fixed at 5 for Phase 6
- "(N more)" overflow indicator — deferred to v2.1
- Project disambiguation when two projects share the same last path segment — rare, deferred
- Per-project cost breakdown (instead of just tokens) — deferred to v2.1

</deferred>

---

*Phase: 06-per-project-breakdown*
*Context gathered: 2026-05-19*
