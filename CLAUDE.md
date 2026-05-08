# Claude Token Tracker — Project Guide

## Project

Fork of Claude-Code-Usage-Monitor adapted for Windows + company plan overage pool tracking.
See `.planning/PROJECT.md` for full context.

## GSD Workflow

This project uses GSD for phase-based execution.

**Current state:** `.planning/STATE.md`
**Roadmap:** `.planning/ROADMAP.md`
**Requirements:** `.planning/REQUIREMENTS.md`

**Next step:** `/gsd-plan-phase 1`

## Key Technical Facts (Read Before Coding)

- **Windows log path:** `%APPDATA%\.claude\projects\` — NOT `~/.claude`. Use `Path(os.environ["APPDATA"]) / ".claude" / "projects"` or `Path.home() / ".claude" / "projects"` with `Path.home()` (not `expanduser`).
- **JSONL deduplication:** Deduplicate by `requestId` before any token counting. Streaming placeholder entries inflate counts 100–174x without this.
- **Cost source:** Use `~/.claude/statusline.jsonl → cost.total_cost_usd`. The `costUSD` field in session JSONL was removed upstream at v1.0.9.
- **Rich on Windows:** Pass `width=shutil.get_terminal_size().columns` explicitly to `Console()`. Auto-detection falls back to 80 columns when stdout is redirected.
- **P90 guard:** Do not activate overage detection until ≥10 sessions of history exist.
- **Cost estimates:** All displayed cost figures must include "est." prefix — they are local approximations, not authoritative billing data.

## Phases

1. **Windows Foundation** — Fork runs on Windows with correct data pipeline and working display
2. **Threshold Detection** — P90 infers included-token limit; cold-start guard prevents false alarms
3. **Overage Pool Dashboard** — INCLUDED/OVERAGE status, pool spend, burn rate, projections, persistence

## GSD Rules

- Read `.planning/STATE.md` at the start of every session
- Execute one phase at a time — do not skip phases
- Commit planning artifacts after each phase transition
- All cost figures in UI must use "est." prefix
