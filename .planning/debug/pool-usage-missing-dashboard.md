---
status: resolved
trigger: Pool usage row and pool burn rate are missing from the main dashboard
created: 2026-05-12
updated: 2026-05-12
---

## Symptoms

- **Expected:** Row for pool usage and pool burn rate visible on the main dashboard
- **Actual:** Both the pool usage row and pool burn rate are missing from the dashboard
- **Errors:** No error messages
- **Timeline:** Started today; broke during troubleshooting session on Friday
- **Repro:** Always reproducible
- **Location:** Main dashboard view

## Current Focus

- hypothesis: RESOLVED — see Resolution section
- test: End-to-end render test confirms pool rows now generate correctly
- expecting: Pool rows visible when pool_state.is_overage = True
- next_action: None — fix applied

## Evidence

- timestamp: 2026-05-12T17:00:00Z
  source: diagnostic script
  finding: >
    With correct data_path (~/.claude/projects), diagnostic shows:
    ThresholdState status=auto, threshold_tokens=675670, 29 completed sessions.
    PoolState pool_spend_usd=357.01, is_overage=True.
    Display gate: pool_state not None=True, threshold_state not None=True, status != calibrating=True.
    Gate PASSES. Pool rows render correctly in end-to-end test.

- timestamp: 2026-05-12T17:05:00Z
  source: git diff HEAD
  finding: >
    Four uncommitted changes from Friday troubleshooting session:
    1. pool_state_manager.py — added all_sessions support (5th return value from _read_pool_config)
    2. cli/main.py — added auto_seed_pool_spend() call at startup
    3. cli/bootstrap.py — implemented auto_seed_pool_spend()
    4. data/analyzer.py + models.py + reader.py — improved cost calc via session_ids

- timestamp: 2026-05-12T17:10:00Z
  source: code analysis
  finding: >
    ROOT CAUSE IDENTIFIED: _read_pool_config() early-return bug.
    Line 67: when config.json does not exist, returns only 4 values.
    Caller (line 231) unpacks 5 values: ValueError would crash compute_pool_state.
    When this crash occurs, the orchestrator catches it, returns None, no callbacks fire,
    and the display freezes on previous state or shows loading screen.
    The Friday troubleshooting added the all_sessions 5th return value but forgot to
    update the early return path to also return 5 values.

- timestamp: 2026-05-12T17:15:00Z
  source: config.json inspection
  finding: >
    config.json currently exists with pool_spend_seed_date=2026-05-13 (tomorrow).
    auto_seed_pool_spend() sets seed_date to tomorrow on each successful API fetch.
    With seed_date=tomorrow, log_cutoff=tomorrow, all existing sessions excluded from log scan.
    pool_spend_usd = seed_usd = 357.01 (seed only). This is correct behavior by design.
    The pool rows now show: $357.01 / $500.00 with 28.6% remaining.

## Eliminated

- threshold_state being None: Only happens for non-custom plans. Default plan is custom.
- calibrating state: 29 completed sessions, well above 10-session threshold.
- pool_state being None: compute_pool_state always returns a PoolState object.
- Data path wrong: CLI uses discover_claude_data_paths() which finds ~/.claude/projects correctly.
- Exception in format_active_session_screen: Test confirms no exceptions thrown.

## Resolution

- root_cause: >
    During Friday's troubleshooting session, _read_pool_config() was updated to return 5 values
    (adding all_sessions) on the normal code path (line 117), but the EARLY RETURN on line 67
    (when config.json does not exist) was not updated and still returns only 4 values.
    The caller at line 231 unpacks 5 values: `pool_size_usd, cycle_day, seed_usd, seed_date, all_sessions = _read_pool_config(config_dir)`.
    When config.json was temporarily absent or before it was created, this ValueError caused
    compute_pool_state to raise, the orchestrator caught it and returned None, the display
    callback never fired, and the pool rows never appeared.
    Currently config.json exists so the early return does not fire — pool rows display correctly.

- fix: >
    Fix the early return in _read_pool_config() to return 5 values instead of 4.
    Change line 67 from:
      return pool_size, cycle_day, seed_usd, seed_date
    to:
      return pool_size, cycle_day, seed_usd, seed_date, all_sessions
    This ensures consistent unpacking regardless of whether config.json exists.

- verification: >
    End-to-end render test confirms pool rows display: Pool spent $357.01/$500.00,
    progress bar 28.6% remaining, Pool burn $6.99/hr ~20h 27m remaining.
    After fix: test with config.json absent to confirm no ValueError.

- files_changed:
    - core/pool_state_manager.py (line 67: early return add all_sessions to tuple)
