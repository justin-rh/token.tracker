# Phase 2: Threshold Detection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 02-threshold-detection
**Areas discussed:** Qualifying sessions, Config file for override, Calibration display, Phase 2 overage signal

---

## Qualifying Sessions

| Option | Description | Selected |
|--------|-------------|----------|
| All completed sessions | Count every finished (non-active, non-gap) session block. Unknown limit means rate-limit filter can't work reliably. | ✓ |
| Only apparent rate-limit hits | Keep ≥95% filter against known limits (19k/88k/220k). Falls back to all sessions if no hits match. | |
| Configurable minimum session count | All sessions for P90 but let user configure the 10-session minimum in config. | |

**User's choice:** All completed sessions
**Notes:** Company plan limit is unknown; the existing rate-limit filter in P90Calculator falls back to all sessions anyway when no hits match known limits. Hardcoded minimum of 10 sessions.

---

## Config File for Override

| Option | Description | Selected |
|--------|-------------|----------|
| Persistent JSON config file | `~/.claude-monitor/config.json` with `overage_threshold_tokens` key. Survives restarts. | ✓ |
| Reuse existing CLI flag | Wire `--custom-limit-tokens` (Settings.custom_limit_tokens). Must pass every run. | |
| Both: file + CLI override | Config file default, CLI flag per-run override. More flexible but merges two sources. | |

**Follow-up — where in the directory:**

| Option | Description | Selected |
|--------|-------------|----------|
| Separate config.json | `~/.claude-monitor/config.json` — distinct from `last_used.json`. | ✓ |
| Merge into last_used.json | Add key to existing file. Mixes intentional config with transient state. | |

**User's choice:** Separate `~/.claude-monitor/config.json`
**Notes:** Clean separation from `last_used.json` which stores transient CLI params.

---

## Calibration Display

| Option | Description | Selected |
|--------|-------------|----------|
| Replace threshold row | Show "Calibrating (N/10 sessions)" where token limit normally appears. Minimal footprint. | ✓ |
| Top-of-dashboard banner | Status bar at top. More visible, takes vertical space. | |
| Inline with sub-note | "P90 calibrating" with count as sub-note. More descriptive, wordier. | |

**Follow-up — post-calibration format:**

| Option | Description | Selected |
|--------|-------------|----------|
| P90 value + 'manual' label | Calibrated: `88,000 tokens (P90)`. Manual: `88,000 tokens (manual)`. | ✓ |
| Separate threshold source row | Extra row below token limit showing source. | |

**User's choice:** Replace threshold row; `(P90)` / `(manual)` suffix on value
**Notes:** Matches success criteria language exactly.

---

## Phase 2 Overage Signal

| Option | Description | Selected |
|--------|-------------|----------|
| Simple INCLUDED/OVERAGE label | One-line status, turns red above threshold. No dollar amounts (Phase 3). | ✓ |
| Threshold progress bar only | Bar turns red at 100%, no explicit label. Phase 3 adds label. | |
| Threshold number only | Just show the inferred number. Leave INCLUDED/OVERAGE entirely to Phase 3. | |

**User's choice:** Simple INCLUDED/OVERAGE label
**Notes:** Foundation for Phase 3 to extend with pool spend + burn rate.

---

## Claude's Discretion

- Rich markup style and exact emoji/color treatment for INCLUDED/OVERAGE
- Whether config.json is read at startup only or each refresh cycle
- Error handling for malformed `overage_threshold_tokens` in config.json

## Deferred Ideas

- Session reset model detection (rolling 5-hour vs calendar-day) — not in Phase 2 requirements; flag for Phase 3
- Configurable cold-start minimum — hardcoded at 10 for Phase 2
