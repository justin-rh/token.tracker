# Phase 8: Burn Rate Accuracy — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 08-burn-rate-accuracy
**Areas discussed:** Rolling window size, Sample insertion policy, Buffer persistence across restarts, Billing cycle reset handling

---

## Rolling Window Size

| Option | Description | Selected |
|--------|-------------|----------|
| 30 minutes | 180 samples at 10s cycles. Responds quickly to spend changes. | ✓ |
| 1 hour | 360 samples. More stable but slower to reflect recent changes. | |
| Configurable in config.json | Adds burn_rate_window_minutes key. | |
| Unbounded (full billing cycle) | Keeps every sample since last billing reset. | |

**User's choice:** 30 minutes
**Notes:** No elaboration needed — recommended option selected.

---

## Sample Insertion Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Only when pool_spend_usd changes | Append only when spend increases from previous sample. Sparse but meaningful. | ✓ |
| Every monitoring cycle (10s) | Append on every cycle regardless of spend change. Buffer fills quickly but mostly identical values. | |

**User's choice:** Only when pool_spend_usd changes
**Notes:** No elaboration needed — recommended option selected.

---

## Buffer Persistence Across Restarts

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory only | Buffer starts empty on restart. Burn rate row hidden until 2 samples accumulate (BURN-02). | ✓ |
| Persist to disk | Serialize to JSON alongside pool_spend.json. Rate available immediately after restart. | |

**User's choice:** In-memory only
**Notes:** No elaboration needed — recommended option selected.

---

## Billing Cycle Reset Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-clear buffer on reset detection | Clear ring buffer when billing_cycle_start changes. | ✓ |
| Filter stale samples by timestamp | Keep buffer, exclude samples from before new billing_cycle_start on read. | |

**User's choice:** Auto-clear buffer on reset detection
**Notes:** No elaboration needed — recommended option selected.

---

## Claude's Discretion

- Attribute naming for new orchestrator state
- Whether to extract burn rate computation into a private helper method

## Deferred Ideas

None.
