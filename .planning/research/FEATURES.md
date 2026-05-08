# Features Research: Claude Token Tracker

**Domain:** Developer tooling — terminal dashboard for Claude Code usage monitoring
**Researched:** 2026-05-07
**Focus:** Company/enterprise plan overage detection and visibility

---

## What the Reference Tool Has (Table Stakes)

These features are already in Maciek-roboblog/Claude-Code-Usage-Monitor v3.1.0 and must be
preserved in the fork. Dropping any of these would be a regression.

| Feature | Implementation | Notes |
|---------|---------------|-------|
| Real-time token consumption display | Rich progress bars, live refresh | Configurable 0.1–20 Hz display rate |
| Burn rate (tokens/hr) | Rolling-window velocity calculation | Multi-threaded data processing |
| Cost estimation | Model-specific pricing lookup | Per-model rates applied to token counts |
| P90 percentile threshold detection | Analyzes last 192 hours of sessions | Avoids requiring user to know their plan limit |
| Session limit predictions | Forecasts when current window will exhaust | Time-to-exhaustion display |
| Multiple view modes | realtime / daily / monthly | Switchable via CLI flag |
| Plan support | Pro / Max5 / Max20 / Custom | Custom uses P90 auto-detection |
| Adaptive theming | Auto-detects light/dark terminal | WCAG-compliant color contrast |
| Responsive layout | Adapts to terminal dimensions | Handles narrow terminals |
| Session window modeling | 5-hour rolling window | Matches Anthropic's actual reset model |
| JSONL log reader | Reads `~/.claude/projects/**/*.jsonl` | Core data source |
| File logging | Configurable severity levels | Optional, off by default |
| Configurable refresh rate | 1–60 second data intervals | Separate from display refresh |
| Timezone auto-detection | System locale respect | 12h/24h format support |

**Confidence:** HIGH — verified against official README and multiple community forks.

---

## What's Missing for the Company Plan Use Case

### The Core Gap: No Overage Pool Concept

The reference tool has no concept of a two-tier budget: "included tokens" vs "extra usage pool."
It models a single limit and a single window. The entire value proposition of this fork is adding
the layer the reference tool is missing.

| Gap | Why It Matters | What's Needed |
|-----|---------------|---------------|
| No included/overage boundary detection | User can't tell when they crossed from included allocation into the $500 pool | Threshold crossing indicator with visual state change |
| No dollar-amount tracking against a fixed pool | "How much of my $500 is spent?" is unanswerable | Cumulative cost-against-pool calculation and display |
| No pool-depletion projection | "When will I exhaust the $500?" is unanswerable | Projection: (remaining pool $) / (current $/hr burn rate) |
| No configurable pool size | Pool is hardcoded nowhere — must be user-settable | Config file field: `overage_pool_usd` (default 500) |
| Windows path assumptions | Reference uses `~/.claude/` which resolves Unix-style; Windows needs `C:\Users\<name>\.claude\` | Windows-aware path resolution |
| No "you are in overage NOW" signal | No alert state or visual mode change at the included/overage boundary | Binary state: INCLUDED vs OVERAGE, displayed prominently |

### The Detection Problem

**Critical finding:** The local JSONL logs and statusline fields do NOT expose whether a session
is billing against the included allocation or the extra usage pool. The `rate_limits.five_hour.used_percentage`
field reaches 100 when the included window is exhausted. But on a Team/Enterprise plan with extra usage
enabled, Claude Code continues working silently after 100% — there is no "extra_usage: true" flag in any
local log file or statusline JSON as of May 2026.

This means the overage boundary must be **inferred**, not directly read:

- **Proxy signal:** `rate_limits.five_hour.used_percentage >= 100` (or the P90 token threshold reached)
- **Stronger proxy:** cumulative session cost within the window exceeds the P90-estimated included value
- **Best approach:** use the P90 threshold as the included/overage boundary, track total cost against that
  threshold, and flag anything above it as drawing from the pool

**Confidence:** HIGH for the detection gap; MEDIUM for the proxy inference approach (it's the best
available without an Anthropic API call, but token undercounting in JSONL affects precision).

### The Token Undercount Problem

JSONL transcript files have a known accuracy issue (confirmed open bug in anthropics/claude-code #22686):

- `usage.input_tokens` is a streaming placeholder — 75% of records contain 0 or 1
- Real input tokens are undercounted by **100–174x**
- Real output tokens are undercounted by **10–17x**
- The `costUSD` field was removed from JSONL in v1.0.9 (was available through v1.0.6)

**Implication for this project:** Raw JSONL token counts cannot be trusted for accurate dollar tracking.
The reference tool's P90 detection works because it looks at *relative* patterns, not absolute counts.
For dollar-accurate overage tracking, the approach used by ccost is better: use model pricing tables
applied to the token fields that ARE reliable (output tokens are more accurate than input tokens),
accept that the result is an estimate, and label it as such in the UI.

**Alternative:** `~/.claude/statusline.jsonl` records server-reported cumulative cost
(`cost.total_cost_usd`) which is computed client-side but is more accurate than raw token math.
This field is the best available cost proxy from local data.

---

## Overage Indicator UX Patterns

### The Single Most Important UI Decision

The primary user question is binary: **"Am I in overage?"** The display must answer this at a glance
without the user having to read numbers. This calls for a state-based display, not just a progress bar.

### Recommended Pattern: Two-State Panel

```
INCLUDED                          OVERAGE
[===================     ] 78%    [          ] $0.00 spent
Time to overage: ~2h 14m          $500.00 remaining

vs.

INCLUDED [================] 100%  OVERAGE [===       ] $47.23 spent
                                  $452.77 remaining (9.4%) | 3h 12m to exhaust
```

The entire panel background or border color changes when state switches from INCLUDED to OVERAGE.
This is more effective than a single progress bar that crosses a threshold line.

### Color Scheme for Status States

Based on terminal UX best practices (green/yellow/red hierarchy) and WCAG contrast requirements:

| State | Color | ANSI | Meaning |
|-------|-------|------|---------|
| INCLUDED — comfortable (< 60% of window) | Green | `\033[32m` | Safe to continue |
| INCLUDED — approaching limit (60–85%) | Yellow | `\033[33m` | Slow down, approaching overage |
| INCLUDED — near limit (> 85%) | Orange/bright yellow | `\033[93m` | Overage imminent |
| OVERAGE — pool < 50% spent | Red | `\033[31m` | Burning pool |
| OVERAGE — pool > 75% spent | Bright red / bold | `\033[91m` | Pool nearly gone |
| OVERAGE — pool exhausted | Bold red + BLOCKED text | `\033[1;91m` | Work will stop |

**Key principle:** The color change at the INCLUDED → OVERAGE boundary must be dramatic and
unmistakable, not subtle. Users are not staring at the dashboard — they glance at it. The state
change must be visible in peripheral vision.

### Progress Bar Design

For the included allocation: standard single bar from 0–100%.

For the overage pool: a second bar that FILLS as money is spent (not depletes), so visually both
bars travel left-to-right. This is less confusing than one bar that empties.

```
Included:  [████████████░░░░░░░░] 61% (resets in 3h 22m)
Pool used: [████░░░░░░░░░░░░░░░░] $94.32 / $500.00 (18.9%)
```

### Status Text Pattern

Leading status label is the highest-value element per terminal UX best practices:

```
STATUS: INCLUDED  |  Burn: $1.84/hr  |  To overage: ~2h 18m
STATUS: OVERAGE   |  Burn: $2.10/hr  |  Pool left: $405.68 (exhausted in ~193h)
```

**Confidence:** MEDIUM — derived from terminal UX best practices and community tool patterns
(usage-bar, vscode-claude-status). No direct prior art for the exact two-state overage pattern
in a Claude token dashboard.

---

## Burn Rate and Projection Features

### What to Calculate

| Calculation | Formula | Display | Why Useful |
|-------------|---------|---------|------------|
| Burn rate ($/hr) | `delta_cost / delta_time` over rolling 15-30 min window | `$2.10/hr` | Answers "how fast am I spending?" |
| Time to overage | `(included_cost_remaining) / burn_rate_$/hr` | `~2h 14m` | When shown while INCLUDED: early warning |
| Time to pool exhaustion | `(pool_remaining_$) / burn_rate_$/hr` | `~193h` | When shown while OVERAGE: depletion ETA |
| Pool % remaining | `(pool_size - pool_spent) / pool_size * 100` | `81.1% remaining` | Quick glance answer to "how much left?" |
| $ spent from pool today | `sum(overage_cost, current_day)` | `$47.23 today` | Daily accountability |
| $ spent from pool this month | `sum(overage_cost, current_month)` | `$94.32 this month` | Monthly budget view |

### Burn Rate Window

Use a **rolling 30-minute window** for the $/hr burn rate calculation (same approach as
vscode-claude-status). Shorter windows (5 min) are too noisy. Longer windows (2 hr) react
too slowly to detect a sudden heavy coding session. 30 minutes balances responsiveness and stability.

Show burn rate as "LOW / MODERATE / HIGH" alongside the numeric value to give context:
- LOW: < $0.50/hr
- MODERATE: $0.50–$3.00/hr
- HIGH: > $3.00/hr

### Projection Caveats

Projections should be labeled as estimates. The pool exhaustion projection in particular can be
wildly off if the user's usage is bursty (heavy for 2 hours, then idle for 6). Consider showing
a range: "at current pace: 47h | at today's peak pace: 12h."

**Confidence:** HIGH for the calculation formulas; MEDIUM for the specific threshold values
(LOW/MODERATE/HIGH burn levels are judgment calls, not empirically derived).

---

## Differentiating Features (Nice to Have)

These are not in the reference tool and would make this fork meaningfully better:

| Feature | Value | Effort | Priority |
|---------|-------|--------|----------|
| Persistent pool spend tracking | Running total of $ spent from the $500 pool across all sessions, stored to a local file so it survives process restarts | Low | HIGH — without this, pool spend resets every dashboard launch |
| Daily overage spend history | Table showing how much was spent from the pool each day | Medium | MEDIUM — useful for spotting high-spend days |
| "Safe to start" indicator | "OK to start a heavy task (est. $12)" vs "CAUTION: only $8 of pool remains" | Low | MEDIUM — actionable decision support |
| Configurable pool size | `overage_pool_usd` in config file, defaults to 500 | Low | HIGH — pool may change; must not require code change |
| Windows-native path resolution | Use `pathlib.Path.home()` to resolve `~/.claude/` correctly on Windows | Low | HIGH — core requirement for this fork |
| "Reset countdown" for included window | "Included allocation resets in 3h 22m" | Low | MEDIUM — already in reference tool for window; keep it |
| Session cost vs pool cost breakdown | This session has cost $X total; $Y from included, $Z from pool | Medium | LOW — useful but complex; defer to v2 |

### Persistent Pool Spend Tracking (Highest Priority Differentiator)

This is the single feature that separates a useful tool from a useless one for the overage use case.
If pool spend is only tracked in-memory, restarting the dashboard loses all context. The fix is
simple: write a local JSON state file (e.g., `~/.claude/token-tracker-state.json`) that persists:

```json
{
  "pool_size_usd": 500.00,
  "pool_spend_usd": 94.32,
  "last_updated": "2026-05-07T14:23:00Z",
  "monthly_period_start": "2026-05-01"
}
```

Reset this at the start of each billing month (or when the user runs `--reset-pool`).

**Confidence:** HIGH for the need; HIGH for the implementation approach.

---

## Anti-Features (Deliberately Exclude)

Features that would add complexity without serving the core use case — or that are explicitly
out of scope per PROJECT.md.

| Anti-Feature | Why Exclude | What to Do Instead |
|--------------|-------------|-------------------|
| Linux/Mac support | Out of scope for v1; adds path and terminal-rendering complexity | Windows-first; document as Windows-only |
| Web UI / browser dashboard | Out of scope; a terminal dashboard covers the need | Keep Rich terminal UI |
| System tray / status bar widget | Out of scope; adds OS integration complexity | A separate tool (jens-duttke/usage-monitor-for-claude) already does this |
| Multi-user / team aggregation | Single-user tool; org-wide rollup requires the admin API | Out of scope v1 |
| Notification alerts (email, Slack, etc.) | Visual dashboard is sufficient; alert plumbing is a large surface area | Out of scope v1 |
| Direct Anthropic API calls for usage data | The `/api/oauth/usage` endpoint is undocumented and rate-limits aggressively (429s reported at even 30-second intervals in issue #31637); using OAuth tokens in third-party tools also violates Anthropic ToS | Stick to local JSONL and statusline.jsonl files |
| Exact billing reconciliation | JSONL token counts are inaccurate (100–174x undercount); cannot match Anthropic's billing exactly | Label all cost figures as estimates; make P90 threshold the proxy |
| Configurable per-model rate tables | API pricing changes frequently; maintaining a local pricing table is a maintenance burden | Accept the reference tool's existing pricing engine; inherit it from the fork |
| GitHub Actions / CI integration | Out of scope for a local developer tool | N/A |
| Historical trend charts | Complex to render in Rich; adds little over the existing daily/monthly table views | Use the reference tool's existing table views |

---

## Confidence Levels

| Finding | Confidence | Basis |
|---------|------------|-------|
| Reference tool feature list | HIGH | Official README + direct inspection |
| JSONL token undercount problem | HIGH | Official GitHub issue #22686 confirmed by Anthropic; multiple community tools acknowledge it |
| `costUSD` field removal in v1.0.9 | HIGH | Confirmed in multiple community articles and issue reports |
| statusline.jsonl `cost.total_cost_usd` field availability | HIGH | Official Claude Code docs (code.claude.com/docs/en/statusline) — full schema confirmed |
| `rate_limits.five_hour.used_percentage` as overage proxy | MEDIUM | Field is in official schema; 100% = included exhausted is inferred, not explicitly documented |
| No "extra_usage" flag in local logs | HIGH | Feature request #25437 explicitly says this data is missing; proposed schema extension not yet shipped |
| `/api/oauth/usage` endpoint rate limiting | HIGH | Two confirmed bug reports (#31637, #31021) with reproduction steps |
| Extra usage is silent (no in-product indicator) | HIGH | Anthropic support docs confirm "seamless continuation"; PROJECT.md confirms user experience |
| Pool spend persistence approach (local JSON file) | MEDIUM | Inferred from first principles; no prior art in the Claude monitoring ecosystem for this specific pattern |
| Burn rate 30-minute window recommendation | MEDIUM | Community tool (vscode-claude-status) uses this; no authoritative source specifies optimal window |
| Two-state panel UX pattern | MEDIUM | Derived from terminal UX best practices; no direct prior art in Claude tooling |

---

## Sources

- [Claude-Code-Usage-Monitor (reference repo)](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor)
- [Claude Code statusline docs — full JSON schema](https://code.claude.com/docs/en/statusline)
- [Feature request: expose account-wide usage to statusline (#25437)](https://github.com/anthropics/claude-code/issues/25437)
- [JSONL token undercount bug (#22686)](https://github.com/anthropics/claude-code/issues/22686)
- [Silent billing change to extra usage (#28927)](https://github.com/anthropics/claude-code/issues/28927)
- [OAuth usage endpoint rate limiting (#31637)](https://github.com/anthropics/claude-code/issues/31637)
- [Manage extra usage for Team/Enterprise plans (Anthropic docs)](https://support.claude.com/en/articles/12005970-manage-extra-usage-for-team-and-seat-based-enterprise-plans)
- [ccost — statusline.jsonl + JSONL dual-source approach](https://github.com/cc-friend/ccost)
- [ccusage cost modes](https://ccusage.com/guide/cost-modes)
- [vscode-claude-status (burn rate + budget tracking reference)](https://github.com/long-910/vscode-claude-status)
- [claude-code-usage-bar (statusline pattern)](https://github.com/leeguooooo/claude-code-usage-bar)
- [jens-duttke Windows tray app (reads OAuth API)](https://github.com/jens-duttke/usage-monitor-for-claude)
- [Evil Martians: CLI UX progress display best practices](https://evilmartians.com/chronicles/cli-ux-best-practices-3-patterns-for-improving-progress-displays)
