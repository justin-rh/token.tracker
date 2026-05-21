# Phase 9: Tray Window Lifecycle — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 09-tray-window-lifecycle
**Areas discussed:** WM_CLOSE interception, Shell vs standalone scope, Restore / focus behavior, Quit vs Hide on window close

---

## WM_CLOSE Interception

| Option | Description | Selected |
|--------|-------------|----------|
| SetWindowLongPtr subclassing | GWLP_WNDPROC subclass — Windows-standard, reliable | ✓ |
| Polling thread | Poll IsWindowVisible every 200ms — hacky, causes flash | |
| Claude's discretion | Let planner choose | |

**User's choice:** SetWindowLongPtr subclassing  
**Notes:** Preferred reliable Windows-standard approach.

---

## Shell vs Standalone Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone-only with detection | Compare window PID to os.getpid(); skip interception if mismatch | ✓ |
| Standalone-only, no detection | Document in README, no code detection | |
| Always intercept | Intercept even in shell — known bad behavior | |

**User's choice:** Standalone-only with detection  
**Notes:** Silent fallback when shell owns the console window.

---

## Restore / Focus Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Always foreground | SetForegroundWindow after ShowWindow | ✓ |
| Show without stealing focus | ShowWindow only | |

**User's choice:** Always foreground

---

## Quit vs Hide on Window Close

| Option | Description | Selected |
|--------|-------------|----------|
| Always hide, no prompt | X = hide. Only Quit via tray exits. | ✓ |
| Prompt on first close | Balloon notification first time | |
| Configurable in config.json | Add hide_to_tray_on_close boolean | |

**User's choice:** Always hide, no prompt  
**Notes:** Same pattern as Slack/Discord.

---

## Claude's Discretion

- Whether to extract WNDPROC setup into `_install_close_guard()` or keep inline in `start()`
- Whether to re-show window on startup if it was hidden at last exit

## Deferred Ideas

None
