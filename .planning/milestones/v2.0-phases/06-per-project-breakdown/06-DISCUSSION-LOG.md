# Phase 6: Per-Project Breakdown - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 06-per-project-breakdown
**Areas discussed:** Project name display, Token counting, Row count / depth, Dashboard placement

---

## Project Name Display

| Option | Description | Selected |
|--------|-------------|----------|
| Last path segment | e.g. `C:-Users-justin-rhoda-token-tracker` → `token-tracker` | ✓ |
| Last two segments | e.g. `rhoda-token-tracker` — disambiguates same-name projects | |
| Raw slug (truncated) | Full directory name, truncated to fit — hardest to read | |

**User's choice:** Last path segment only
**Notes:** Clean and short; matches how the user thinks of the project name.

---

## Token Counting

| Option | Description | Selected |
|--------|-------------|----------|
| Total tokens | input + output + cache_creation + cache_read; matches `TokenCounts.total_tokens` | ✓ |
| Input + output only | Excludes cache tokens; cache-heavy projects rank lower | |
| Output tokens only | Ranks by Claude generation volume only | |

**User's choice:** Total tokens
**Notes:** Represents full API cost footprint; reuses existing `total_tokens` property — no new math.

---

## Row Count / Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Top 5 | Compact, covers most days; fixed value | ✓ |
| Top 3 | Most compact | |
| Configurable (default 5) | Adds `project_breakdown_rows` config key | |

**User's choice:** Top 5 (fixed)
**Notes:** No config option needed for Phase 6.

---

## Dashboard Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Side-by-side columns, below Pool Spent | Cost first, then breakdown as drill-down | ✓ |
| Side-by-side columns, above Pool Spent | Breakdown before cost impact | |

**User's additional decisions (freeform clarification):**
- Remove rows: Cost Usage, Token Usage, Messages Usage, Time to Reset
- Move rows: Model Distribution, Burn Rate, Cost Rate → below Last web sync line
- Two lists (today / billing month) appear as side-by-side columns in one section block

**Notes:** User specified these layout changes proactively. The restructure and the per-project feature are delivered together in Phase 6.

---

## Claude's Discretion

- Exact column widths, padding, and alignment for side-by-side layout
- Whether to show `(N more)` indicator when projects exceed 5
- Token display format (e.g. `88,420 tok` vs `88.4k tok`)
- Whether `compute_project_breakdown` runs every 10s cycle or less frequently

## Deferred Ideas

- Configurable row count (`project_breakdown_rows`)
- `(N more)` overflow indicator
- Project name disambiguation for same last-segment collisions
- Per-project cost breakdown (not just tokens)
