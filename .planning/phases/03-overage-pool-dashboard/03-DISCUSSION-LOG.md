# Phase 3: Overage Pool Dashboard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 03-overage-pool-dashboard
**Areas discussed:** Pool spend accounting, State persistence, Burn rate window

---

## Pool Spend Accounting

| Option | Description | Selected |
|--------|-------------|----------|
| Sum OVERAGE session costs | Sum statusline.jsonl cost.total_cost_usd for sessions in billing period where tokens > threshold | ✓ |
| Total cost minus included allocation | Sum all session costs, subtract estimated included-token dollar value | |
| Accumulator-only (live tracking) | Only count overage cost while tool is running | |

**User's choice:** Sum OVERAGE session costs

---

| Option | Description | Selected |
|--------|-------------|----------|
| Count the full session cost | Simpler; slight over-estimate acceptable given "est." prefix | ✓ |
| Count only the marginal overage cost | Estimate tokens above threshold × avg_cost_per_token; more accurate but complex | |
| You decide | Leave to Claude during planning | |

**User's choice:** Count the full session cost

**Notes:** Both choices favor simplicity. Slight over-estimation is acceptable because all figures are prefixed "est." anyway (DISP-02).

---

## State Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Persist derived pool state | Write pool_spend.json with pool_spend_usd + billing_cycle_start; recompute from logs on startup | ✓ |
| Persist an accumulator total | Write and increment running total; can drift if sessions are missed | |
| Derive fresh, no file | Recompute every refresh; risk: lost if statusline.jsonl is trimmed | |

**User's choice:** Persist derived pool state

---

| Option | Description | Selected |
|--------|-------------|----------|
| In config.json alongside pool_size | billing_cycle_start_day (int 1–28) added to existing config.json | ✓ |
| In pool_spend.json state file | User would need to edit a state file to change billing cycle — unexpected | |

**User's choice:** In config.json alongside pool_size

**Notes:** Keeps all user-editable settings in one place, consistent with Phase 2 config.json pattern.

---

## Burn Rate Window

| Option | Description | Selected |
|--------|-------------|----------|
| Active session rate | $/hr from current session cost ÷ elapsed minutes | ✓ |
| Billing period average | Total pool spend ÷ days elapsed; smoothed, less reactive | |
| Rolling last 7 days | Average daily overage over past week; adds bucketing complexity | |

**User's choice:** Active session rate

---

| Option | Description | Selected |
|--------|-------------|----------|
| OVERAGE only | Show burn rate and projection only while actively burning the pool | ✓ |
| Always show | Show even when INCLUDED; likely confusing | |

**User's choice:** OVERAGE only

---

## Claude's Discretion

- Exact Rich markup, emoji, and row label text (consistent with session_display.py style)
- Write frequency for pool_spend.json (each refresh vs startup/shutdown only)
- Error fallback if statusline.jsonl missing
- Whether to introduce PoolStateManager class vs inline logic

## Deferred Ideas

- Session reset model detection (rolling 5h vs calendar-day) — not needed for Phase 3 pool tracking
- Billing API integration (v2 BILL-01)
- Pool % alert threshold (v2 BILL-02)
- Historical pool spend chart (v2 ANLX-01)
