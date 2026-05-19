"""Simplified CLI entry point using pydantic-settings."""

import argparse
import contextlib
import json
import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, NoReturn, Optional, Union

from rich.console import Console

from claude_monitor import __version__
from claude_monitor.cli.bootstrap import (
    auto_seed_pool_spend,
    ensure_directories,
    init_timezone,
    setup_environment,
    setup_logging,
)
from claude_monitor.core.plans import Plans, PlanType, get_token_limit
from claude_monitor.core.settings import Settings
from claude_monitor.data.aggregator import UsageAggregator
from claude_monitor.data.analysis import analyze_usage
from claude_monitor.error_handling import report_error
from claude_monitor.monitoring.orchestrator import MonitoringOrchestrator
from claude_monitor.monitoring.web_poller import WebPoller
from claude_monitor.ui.tray_manager import TrayManager
from claude_monitor.core.usage_fetcher import (
    _migrate_config_to_keyring,
    _read_auth_cookies,
    _discover_org_id,
)
from claude_monitor.terminal.manager import (
    enter_alternate_screen,
    handle_cleanup_and_exit,
    handle_error_and_exit,
    restore_terminal,
    setup_terminal,
)
from claude_monitor.terminal.themes import get_themed_console, print_themed
from claude_monitor.ui.display_controller import DisplayController
from claude_monitor.ui.table_views import TableViewsController

# Type aliases for CLI callbacks
DataUpdateCallback = Callable[[Dict[str, Any]], None]
SessionChangeCallback = Callable[[str, str, Optional[Dict[str, Any]]], None]


def get_standard_claude_paths() -> List[str]:
    """Get list of standard Claude data directory paths to check."""
    return ["~/.claude/projects", "~/.config/claude/projects"]


def discover_claude_data_paths(custom_paths: Optional[List[str]] = None) -> List[Path]:
    """Discover all available Claude data directories.

    Args:
        custom_paths: Optional list of custom paths to check instead of standard ones

    Returns:
        List of Path objects for existing Claude data directories
    """
    paths_to_check: List[str] = (
        [str(p) for p in custom_paths] if custom_paths else get_standard_claude_paths()
    )

    discovered_paths: List[Path] = []

    for path_str in paths_to_check:
        path = Path(path_str).expanduser().resolve()
        if path.exists() and path.is_dir():
            discovered_paths.append(path)

    return discovered_paths


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point with direct pydantic-settings integration."""
    if argv is None:
        argv = sys.argv[1:]

    if "--version" in argv or "-v" in argv:
        print(f"claude-monitor {__version__}")
        return 0

    try:
        settings = Settings.load_with_last_used(argv)

        setup_environment()
        ensure_directories()
        auto_seed_pool_spend()

        if settings.log_file:
            setup_logging(settings.log_level, settings.log_file, disable_console=True)
        else:
            setup_logging(settings.log_level, disable_console=True)

        init_timezone(settings.timezone)

        args = settings.to_namespace()

        _run_monitoring(args)

        return 0

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        return 0
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Monitor failed: {e}", exc_info=True)
        traceback.print_exc()
        return 1


def _tray_shutdown() -> None:
    """Trigger clean shutdown from pystray thread (identical to Ctrl+C).

    Per RESEARCH.md Pitfall 2-3: use CTRL_C_EVENT not SIGINT on Windows.
    signal is already imported at the top of this module.
    """
    os.kill(os.getpid(), signal.CTRL_C_EVENT)


def _run_monitoring(args: argparse.Namespace) -> None:
    """Main monitoring implementation without facade."""
    view_mode = getattr(args, "view", "realtime")

    if hasattr(args, "theme") and args.theme:
        console = get_themed_console(force_theme=args.theme.lower())
    else:
        console = get_themed_console()

    old_terminal_settings = setup_terminal()
    live_display_active: bool = False

    try:
        data_paths: List[Path] = discover_claude_data_paths()
        if not data_paths:
            print_themed("No Claude data directory found", style="error")
            return

        data_path: Path = data_paths[0]
        logger = logging.getLogger(__name__)
        logger.info(f"Using data path: {data_path}")

        # Handle different view modes
        if view_mode in ["daily", "monthly"]:
            _run_table_view(args, data_path, view_mode, console)
            return

        token_limit: int = _get_initial_token_limit(args, str(data_path))

        display_controller = DisplayController()
        display_controller.live_manager._console = console

        refresh_per_second: float = getattr(args, "refresh_per_second", 0.75)
        logger.info(
            f"Display refresh rate: {refresh_per_second} Hz ({1000 / refresh_per_second:.0f}ms)"
        )
        logger.info(f"Data refresh rate: {args.refresh_rate} seconds")

        live_display = display_controller.live_manager.create_live_display(
            auto_refresh=True, console=console, refresh_per_second=refresh_per_second
        )

        loading_display = display_controller.create_loading_display(
            args.plan, args.timezone
        )

        enter_alternate_screen()

        # Phase 4: Auth setup MUST complete before Rich Live context opens (Pitfall 5)
        config_dir = Path.home() / ".claude-monitor"
        session_key, org_id = _setup_auth(config_dir)

        live_display_active = False

        try:
            # Enter live context and show loading screen immediately
            live_display.__enter__()
            live_display_active = True
            live_display.update(loading_display)

            orchestrator = MonitoringOrchestrator(
                update_interval=(
                    args.refresh_rate if hasattr(args, "refresh_rate") else 10
                ),
                data_path=str(data_path),
            )
            orchestrator.set_args(args)

            # Phase 4: Start WebPoller daemon thread (D-12, D-14)
            web_poller = None
            if org_id:
                web_poller = WebPoller(org_id, config_dir)
                web_poller.start()
                orchestrator.set_web_poller(web_poller)

            # Phase 5: Start system tray icon (TRAY-01 through TRAY-05)
            tray_manager = TrayManager(shutdown_callback=_tray_shutdown)
            tray_manager.start()

            # Setup monitoring callback
            def on_data_update(monitoring_data: Dict[str, Any]) -> None:
                """Handle data updates from orchestrator."""
                try:
                    data: Dict[str, Any] = monitoring_data.get("data", {})
                    blocks: List[Dict[str, Any]] = data.get("blocks", [])

                    logger.debug(f"Display data has {len(blocks)} blocks")
                    if blocks:
                        active_blocks: List[Dict[str, Any]] = [
                            b for b in blocks if b.get("isActive")
                        ]
                        logger.debug(f"Active blocks: {len(active_blocks)}")
                        if active_blocks:
                            total_tokens: int = active_blocks[0].get("totalTokens", 0)
                            logger.debug(f"Active block tokens: {total_tokens}")

                    renderable = display_controller.create_data_display(
                        data,
                        args,
                        monitoring_data.get("token_limit", token_limit),
                        threshold_state=monitoring_data.get("threshold_state"),
                        pool_state=monitoring_data.get("pool_state"),          # Phase 3 NEW
                        web_usage=monitoring_data.get("web_usage"),            # Phase 4 NEW
                        last_web_sync=monitoring_data.get("last_web_sync"),    # Phase 4 NEW
                    )

                    if live_display:
                        live_display.update(renderable)

                    # Phase 5: Update tray icon color and tooltip (TRAY-01, TRAY-02)
                    web_usage = monitoring_data.get("web_usage")
                    if tray_manager is not None:
                        tray_manager.update(
                            utilization_pct=web_usage.utilization_pct if web_usage else None,
                            last_sync=monitoring_data.get("last_web_sync"),
                        )

                except Exception as e:
                    logger.error(f"Display update error: {e}", exc_info=True)
                    report_error(
                        exception=e,
                        component="cli_main",
                        context_name="display_update_error",
                    )

            # Register callbacks
            orchestrator.register_update_callback(on_data_update)

            # Optional: Register session change callback
            def on_session_change(
                event_type: str, session_id: str, session_data: Optional[Dict[str, Any]]
            ) -> None:
                """Handle session changes."""
                if event_type == "session_start":
                    logger.info(f"New session detected: {session_id}")
                elif event_type == "session_end":
                    logger.info(f"Session ended: {session_id}")

            orchestrator.register_session_callback(on_session_change)

            # Start monitoring
            orchestrator.start()

            # Wait for initial data
            logger.info("Waiting for initial data...")
            if not orchestrator.wait_for_initial_data(timeout=10.0):
                logger.warning("Timeout waiting for initial data")

            # Main loop - live display is already active
            # Use signal.pause() for more efficient waiting
            try:
                signal.pause()
            except (AttributeError, OSError):
                # Fallback for Windows: signal.pause() raises OSError on Windows
                while True:
                    time.sleep(1)
        finally:
            # Stop monitoring first
            if "orchestrator" in locals():
                orchestrator.stop()

            # Phase 4: Stop WebPoller daemon thread (signals Event; thread exits on next wake)
            if "web_poller" in locals() and web_poller is not None:
                web_poller.stop()

            # Phase 5: Stop tray icon (TRAY-05 — no ghost icons)
            if "tray_manager" in locals() and tray_manager is not None:
                tray_manager.stop()

            # Exit live display context if it was activated
            if live_display_active:
                with contextlib.suppress(Exception):
                    live_display.__exit__(None, None, None)

    except KeyboardInterrupt:
        # Stop tray icon if the inner finally block was skipped
        if "tray_manager" in locals() and tray_manager is not None:
            with contextlib.suppress(Exception):
                tray_manager.stop()
        # Clean exit from live display if it's active
        if "live_display" in locals():
            with contextlib.suppress(Exception):
                live_display.__exit__(None, None, None)
        handle_cleanup_and_exit(old_terminal_settings)
    except Exception as e:
        # Clean exit from live display if it's active
        if "live_display" in locals():
            with contextlib.suppress(Exception):
                live_display.__exit__(None, None, None)
        handle_error_and_exit(old_terminal_settings, e)
    finally:
        restore_terminal(old_terminal_settings)


def _get_initial_token_limit(
    args: argparse.Namespace, data_path: Union[str, Path]
) -> int:
    """Get initial token limit for the plan."""
    logger = logging.getLogger(__name__)
    plan: str = getattr(args, "plan", PlanType.PRO.value)

    # For custom plans, check if custom_limit_tokens is provided first
    if plan == "custom":
        # If custom_limit_tokens is explicitly set, use it
        if hasattr(args, "custom_limit_tokens") and args.custom_limit_tokens:
            custom_limit = int(args.custom_limit_tokens)
            print_themed(
                f"Using custom token limit: {custom_limit:,} tokens",
                style="info",
            )
            return custom_limit

        # Otherwise, analyze usage data to calculate P90
        print_themed("Analyzing usage data to determine cost limits...", style="info")

        try:
            # Use quick start mode for faster initial load
            usage_data: Optional[Dict[str, Any]] = analyze_usage(
                hours_back=96 * 2,
                quick_start=False,
                use_cache=False,
                data_path=str(data_path),
            )

            if usage_data and "blocks" in usage_data:
                blocks: List[Dict[str, Any]] = usage_data["blocks"]
                token_limit: int = get_token_limit(plan, blocks)

                print_themed(
                    f"P90 session limit calculated: {token_limit:,} tokens",
                    style="info",
                )

                return token_limit

        except Exception as e:
            logger.warning(f"Failed to analyze usage data: {e}")

        # Fallback to default limit
        print_themed("Using default limit as fallback", style="warning")
        return Plans.DEFAULT_TOKEN_LIMIT

    # For standard plans, just get the limit
    return get_token_limit(plan)


def _setup_auth(config_dir: Path) -> tuple:
    """Resolve authentication before the Rich Live display starts.

    MUST be called BEFORE live_display.__enter__() — console input() is
    incompatible with the Rich Live rendering context (Pitfall 5 in RESEARCH.md).

    Implements D-04 (migration), D-06 (priority order), D-08 (manual paste prompt),
    D-09 (org_id discovery), D-10 (stale key clear + re-prompt), D-11 (keyring read).

    Returns (session_key, org_id). Either may be None if setup failed.
    """
    import keyring

    _migrate_config_to_keyring(config_dir)  # D-04: one-time migration

    # Read config.json for org_id
    config_file = config_dir / "config.json"
    try:
        cfg = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    except Exception:
        cfg = {}

    MAX_AUTH_ATTEMPTS = 3
    attempts = 0
    while attempts < MAX_AUTH_ATTEMPTS:
        attempts = attempts + 1
        session_key, _cf = _read_auth_cookies(config_dir)  # D-06 priority order

        if session_key:
            # D-10: Stale key check — verify the key works before launching dashboard.
            # _discover_org_id() makes a real API call; None means 401/403 (stale key)
            # or genuine network failure. We treat None as "key may be stale" and
            # only clear+re-prompt when org_id is also unknown (key is our only auth signal).
            org_id = cfg.get("org_id")
            if not org_id:
                discovered = _discover_org_id(session_key)
                if discovered:
                    org_id = discovered
                    cfg["org_id"] = org_id
                    try:
                        config_dir.mkdir(parents=True, exist_ok=True)
                        tmp = config_file.with_suffix(".tmp")
                        tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
                        tmp.replace(config_file)
                    except Exception as exc:
                        logging.getLogger(__name__).warning(
                            "auth: failed to write org_id to config.json: %s", exc
                        )
                else:
                    # D-10: _discover_org_id() returned None — sessionKey may be stale.
                    # Clear from keyring and fall through to D-08 paste prompt.
                    try:
                        keyring.delete_password("claude-monitor", "sessionKey")
                    except keyring.errors.PasswordDeleteError:
                        pass
                    logging.getLogger(__name__).info(
                        "auth: stale sessionKey cleared — re-prompting"
                    )
                    session_key = None
                    # Fall through to D-08 prompt below
            if session_key:
                return session_key, org_id

        # D-08: No sessionKey available (or stale key cleared above).
        # Block dashboard launch and prompt for manual paste.
        print("\nWeb auth required.")
        print("1. Open claude.ai in your browser")
        print("2. Open DevTools (F12) → Application → Cookies → claude.ai")
        print("3. Copy the value of the 'sessionKey' cookie")
        print()
        try:
            pasted = input("Paste sessionKey here: ").strip() or None
        except (EOFError, KeyboardInterrupt):
            return None, cfg.get("org_id")
        if pasted:
            try:
                keyring.set_password("claude-monitor", "sessionKey", pasted)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "auth: failed to store sessionKey in keyring: %s", exc
                )
            session_key = pasted
            # D-09: Attempt org_id discovery with the newly pasted key
            org_id = cfg.get("org_id")
            if not org_id:
                discovered = _discover_org_id(session_key)
                if discovered:
                    org_id = discovered
                    cfg["org_id"] = org_id
                    try:
                        config_dir.mkdir(parents=True, exist_ok=True)
                        tmp = config_file.with_suffix(".tmp")
                        tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
                        tmp.replace(config_file)
                    except Exception as exc:
                        logging.getLogger(__name__).warning(
                            "auth: failed to write org_id to config.json: %s", exc
                        )
                else:
                    # D-09: Auto-discovery failed — prompt user for org_id
                    print("\nOrg ID required (auto-discovery failed).")
                    print("Find it in: claude.ai → Settings → Account → Organization ID")
                    print()
                    try:
                        org_id = input("Paste org_id here: ").strip() or None
                    except (EOFError, KeyboardInterrupt):
                        org_id = None
                    if org_id:
                        cfg["org_id"] = org_id
                        try:
                            config_dir.mkdir(parents=True, exist_ok=True)
                            tmp = config_file.with_suffix(".tmp")
                            tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
                            tmp.replace(config_file)
                        except Exception as exc:
                            logging.getLogger(__name__).warning(
                                "auth: failed to write org_id to config.json: %s", exc
                            )
            return session_key, org_id
        # If user pressed Enter with no input, loop and try again

    logging.getLogger(__name__).warning("auth: max attempts reached — launching without web auth")
    return None, cfg.get("org_id")


def handle_application_error(
    exception: Exception,
    component: str = "cli_main",
    exit_code: int = 1,
) -> NoReturn:
    """Handle application-level errors with proper logging and exit.

    Args:
        exception: The exception that occurred
        component: Component where the error occurred
        exit_code: Exit code to use when terminating
    """
    logger = logging.getLogger(__name__)

    # Log the error with traceback
    logger.error(f"Application error in {component}: {exception}", exc_info=True)

    # Report to error handling system
    from claude_monitor.error_handling import report_application_startup_error

    report_application_startup_error(
        exception=exception,
        component=component,
        additional_context={
            "exit_code": exit_code,
            "args": sys.argv,
        },
    )

    # Print user-friendly error message
    print(f"\nError: {exception}", file=sys.stderr)
    print("For more details, check the log files.", file=sys.stderr)

    sys.exit(exit_code)


def validate_cli_environment() -> Optional[str]:
    """Validate the CLI environment and return error message if invalid.

    Returns:
        Error message if validation fails, None if successful
    """
    try:
        # Check Python version compatibility
        if sys.version_info < (3, 8):
            return f"Python 3.8+ required, found {sys.version_info.major}.{sys.version_info.minor}"

        # Check for required dependencies
        required_modules = ["rich", "pydantic"]
        missing_modules: List[str] = []

        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)

        if missing_modules:
            return f"Missing required modules: {', '.join(missing_modules)}"

        return None

    except Exception as e:
        return f"Environment validation failed: {e}"


def _run_table_view(
    args: argparse.Namespace, data_path: Path, view_mode: str, console: Console
) -> None:
    """Run table view mode (daily/monthly)."""
    logger = logging.getLogger(__name__)

    try:
        # Create aggregator with appropriate mode
        aggregator = UsageAggregator(
            data_path=str(data_path),
            aggregation_mode=view_mode,
            timezone=args.timezone,
        )

        # Create table controller
        controller = TableViewsController(console=console)

        # Get aggregated data
        logger.info(f"Loading {view_mode} usage data...")
        aggregated_data = aggregator.aggregate()

        if not aggregated_data:
            print_themed(f"No usage data found for {view_mode} view", style="warning")
            return

        # Display the table
        controller.display_aggregated_view(
            data=aggregated_data,
            view_mode=view_mode,
            timezone=args.timezone,
            plan=args.plan,
            token_limit=_get_initial_token_limit(args, data_path),
        )

        # Wait for user to press Ctrl+C
        print_themed("\nPress Ctrl+C to exit", style="info")
        try:
            # Use signal.pause() for more efficient waiting
            try:
                signal.pause()
            except (AttributeError, OSError):
                # Fallback for Windows: signal.pause() raises OSError on Windows
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print_themed("\nExiting...", style="info")

    except Exception as e:
        logger.error(f"Error in table view: {e}", exc_info=True)
        print_themed(f"Error displaying {view_mode} view: {e}", style="error")


if __name__ == "__main__":
    sys.exit(main())
