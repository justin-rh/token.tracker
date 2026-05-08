# Phase 1: Windows Foundation - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Port the Claude-Code-Usage-Monitor Python tool to run correctly on Windows: correct log path resolution, JSONL deduplication by requestId, accurate cost figures from statusline.jsonl, and a full-width Rich dashboard. No overage pool logic in this phase — data pipeline and display only.

</domain>

<decisions>
## Implementation Decisions

### Code Layout
- **D-01:** Forked code lives at the **repo root** — no subdirectory. All source files (reader.py, analyzer.py, etc.) copied directly alongside CLAUDE.md.
- **D-02:** Entry point is `python monitor.py` — a single root-level file that imports from the package modules. No install step required; run from repo root.

### Windows Path Resolution
- **D-03:** Use `Path(os.environ["APPDATA"]) / ".claude" / "projects"` as the canonical log path on Windows. This is the explicit, correct approach — `APPDATA` is always set on Windows 11 and points to `AppData\Roaming`. Do NOT use `Path.home()` (wrong location) or `expanduser("~")` (resolves to USERPROFILE, not AppData).
- **D-04:** No env-var override for the log path in Phase 1 — keep it simple. Add `CLAUDE_CONFIG_DIR` override in a future phase if needed.

### Active Session File Handling (WinError 32)
- **D-05:** When a JSONL file raises `PermissionError` (WinError 32 — Claude Code holds it open), **skip the file and display an "(active session — data not yet visible)" indicator** in the dashboard. Do not try to force-read with win32 flags. Do not skip silently — the user needs to know current session data is excluded.

### Cost Source (statusline.jsonl)
- **D-06:** **statusline.jsonl is the primary cost source.** Read `cost.total_cost_usd` from `~/.claude/statusline.jsonl`. Fall back to the reference tool's pricing engine only when statusline.jsonl is missing or has no entry for a session.
- **D-07:** statusline.jsonl is expected to have **one entry per session** (JSONL format — each line is a JSON record). Match entries to session blocks by session ID or timestamp. If the structure turns out to be different when reading the actual file, adapt the integration strategy at that point.
- **D-08:** The reference tool's `costUSD` field (in session JSONL) is NOT used — it was removed at v1.0.9 upstream. Do not attempt to read it.

### Claude's Discretion
- Deduplication implementation detail: whether to deduplicate requestIds at read time (in reader.py) or post-parse is Claude's call — the requirement is just that deduplication happens before token counting.
- Rich dashboard width: pass `width=shutil.get_terminal_size().columns` to `Console()` — implementation detail of where exactly in the code this is wired.
- Exact wording of the "(active session)" indicator — Claude's discretion on phrasing and placement in the dashboard.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research (Pre-existing, from project initialization)
- `.planning/research/PITFALLS.md` — Critical Windows-specific pitfalls: path handling, Rich rendering, file locking (WinError 32), requestId deduplication. **Read before writing any code.**
- `.planning/research/ARCHITECTURE.md` — Reference tool component map, data flow, and overage layer integration point. Shows exactly which files to touch.
- `.planning/research/STACK.md` — Python version, dependency list, Rich version, and other stack facts.
- `.planning/research/FEATURES.md` — Reference tool feature inventory.

### Project Context
- `.planning/REQUIREMENTS.md` — Requirements PORT-01, PORT-02, PORT-03, PORT-04, DISP-01 are in scope for this phase. Read for acceptance criteria details.
- `CLAUDE.md` — Key technical facts: Windows path, deduplication, cost source, Rich width, P90 guard. These are project-level constraints that apply here.

### External Reference
- Upstream tool: `github.com/Maciek-roboblog/Claude-Code-Usage-Monitor` (v3.1.0) — source to fork from.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — no source code exists in this repo. All files come from the upstream fork.

### Established Patterns
- Reference tool uses Rich library for terminal UI — keep this, it's the proven foundation.
- Reference tool's `reader.py` uses `Path(data_path).expanduser()` — this is the single line to replace with the Windows AppData path logic.
- `data_manager.py` has a 30-second TTL cache around `analyze_usage()` — this is the refresh mechanism for DISP-01.

### Integration Points
- `reader.py` — primary file to modify for Windows path (PORT-01) and file-lock handling.
- `reader.py` or `data/parser.py` — add requestId deduplication (PORT-02).
- Cost attribution layer (wherever `costUSD` was read) — replace with statusline.jsonl read (PORT-03).
- `ui/display_controller.py` or `Console()` instantiation — add explicit terminal width (PORT-04).

</code_context>

<specifics>
## Specific Ideas

- The CLAUDE.md note: "Use `Path(os.environ["APPDATA"]) / ".claude" / "projects"`" — this is the exact code pattern to use, not just a concept.
- PITFALLS.md mentions `WinError 32` PermissionError specifically — wrap all JSONL file opens in `try/except PermissionError` and surface the "(active session)" indicator.
- statusline.jsonl is at `~/.claude/statusline.jsonl` (user's home `.claude` dir, not the projects subdir).

</specifics>

<deferred>
## Deferred Ideas

- `CLAUDE_CONFIG_DIR` env var override for non-standard install paths — future phase if needed.
- MAX_PATH (260 char limit) handling — PITFALLS.md flags this as moderate risk; defer until it surfaces with real data.
- Cross-platform path stubs for future Linux/Mac support — out of scope for v1.

</deferred>

---

*Phase: 01-windows-foundation*
*Context gathered: 2026-05-08*
