"""Session display components for Claude Monitor.

Handles formatting of active session screens and session data display.
"""

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, Optional

import pytz

from claude_monitor.ui.components import CostIndicator, VelocityIndicator
from claude_monitor.ui.layouts import HeaderManager
from claude_monitor.ui.progress_bars import (
    ModelUsageBar,
    TimeProgressBar,
    TokenProgressBar,
)
from claude_monitor.utils.time_utils import (
    format_display_time,
    get_time_format_preference,
    percentage,
)


import re as _re
import unicodedata as _ud


def _fmt_tokens(n: int) -> str:
    """Format token count: M for millions, k for thousands, plain otherwise."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M tok"
    if n >= 1000:
        return f"{n / 1000:.1f}k tok"
    return f"{n} tok"


def _col_pad(s: str, width: int) -> str:
    """Pad s so its terminal-visible width reaches `width`.

    f-string :<N counts Python string length, not terminal columns.
    Rich markup tags ([value], [dim], [/]) are invisible but add string length.
    Wide chars like 📂 occupy 2 columns but are 1 Python char.
    """
    stripped = _re.sub(r'\[/?[^\]]*\]', '', s)
    visible = sum(2 if _ud.east_asian_width(c) in ('W', 'F') else 1 for c in stripped)
    return s + ' ' * max(0, width - visible)


@dataclass
class SessionDisplayData:
    """Data container for session display information.

    This replaces the 21 parameters in format_active_session_screen method.
    """

    plan: str
    timezone: str
    tokens_used: int
    token_limit: int
    usage_percentage: float
    tokens_left: int
    elapsed_session_minutes: float
    total_session_minutes: float
    burn_rate: float
    session_cost: float
    per_model_stats: dict[str, Any]
    sent_messages: int
    entries: list[dict]
    predicted_end_str: str
    reset_time_str: str
    current_time_str: str
    show_switch_notification: bool = False
    show_exceed_notification: bool = False
    show_tokens_will_run_out: bool = False
    original_limit: int = 0


class SessionDisplayComponent:
    """Main component for displaying active session information."""

    def __init__(self):
        """Initialize session display component with sub-components."""
        self.token_progress = TokenProgressBar()
        self.time_progress = TimeProgressBar()
        self.model_usage = ModelUsageBar()

    def _render_wide_progress_bar(self, percentage: float) -> str:
        """Render a wide progress bar (50 chars) using centralized progress bar logic.

        Args:
            percentage: Progress percentage (can be > 100)

        Returns:
            Formatted progress bar string
        """
        from claude_monitor.terminal.themes import get_cost_style

        if percentage < 50:
            color = "🟢"
        elif percentage < 80:
            color = "🟡"
        else:
            color = "🔴"

        progress_bar = TokenProgressBar(width=50)
        bar_style = get_cost_style(percentage)

        capped_percentage = min(percentage, 100.0)
        filled = progress_bar._calculate_filled_segments(capped_percentage, 100.0)

        if percentage >= 100:
            filled_bar = progress_bar._render_bar(50, filled_style=bar_style)
        else:
            filled_bar = progress_bar._render_bar(
                filled, filled_style=bar_style, empty_style="table.border"
            )

        return f"{color} [{filled_bar}]"

    def format_active_session_screen_v2(self, data: SessionDisplayData) -> list[str]:
        """Format complete active session screen using data class.

        This is the refactored version using SessionDisplayData.

        Args:
            data: SessionDisplayData object containing all display information

        Returns:
            List of formatted lines for display
        """
        return self.format_active_session_screen(
            plan=data.plan,
            timezone=data.timezone,
            tokens_used=data.tokens_used,
            token_limit=data.token_limit,
            usage_percentage=data.usage_percentage,
            tokens_left=data.tokens_left,
            elapsed_session_minutes=data.elapsed_session_minutes,
            total_session_minutes=data.total_session_minutes,
            burn_rate=data.burn_rate,
            session_cost=data.session_cost,
            per_model_stats=data.per_model_stats,
            sent_messages=data.sent_messages,
            entries=data.entries,
            predicted_end_str=data.predicted_end_str,
            reset_time_str=data.reset_time_str,
            current_time_str=data.current_time_str,
            show_switch_notification=data.show_switch_notification,
            show_exceed_notification=data.show_exceed_notification,
            show_tokens_will_run_out=data.show_tokens_will_run_out,
            original_limit=data.original_limit,
        )

    def format_active_session_screen(
        self,
        plan: str,
        timezone: str,
        tokens_used: int,
        token_limit: int,
        usage_percentage: float,
        tokens_left: int,
        elapsed_session_minutes: float,
        total_session_minutes: float,
        burn_rate: float,
        session_cost: float,
        per_model_stats: dict[str, Any],
        sent_messages: int,
        entries: list[dict],
        predicted_end_str: str,
        reset_time_str: str,
        current_time_str: str,
        show_switch_notification: bool = False,
        show_exceed_notification: bool = False,
        show_tokens_will_run_out: bool = False,
        original_limit: int = 0,
        **kwargs,
    ) -> list[str]:
        """Format complete active session screen.

        Args:
            plan: Current plan name
            timezone: Display timezone
            tokens_used: Number of tokens used
            token_limit: Token limit for the plan
            usage_percentage: Usage percentage
            tokens_left: Remaining tokens
            elapsed_session_minutes: Minutes elapsed in session
            total_session_minutes: Total session duration
            burn_rate: Current burn rate
            session_cost: Session cost in USD
            per_model_stats: Model usage statistics
            sent_messages: Number of messages sent
            entries: Session entries
            predicted_end_str: Predicted end time string
            reset_time_str: Reset time string
            current_time_str: Current time string
            show_switch_notification: Show plan switch notification
            show_exceed_notification: Show exceed limit notification
            show_tokens_will_run_out: Show token depletion warning
            original_limit: Original plan limit

        Returns:
            List of formatted screen lines
        """

        screen_buffer = []

        header_manager = HeaderManager()
        screen_buffer.extend(header_manager.create_header(plan, timezone))

        if plan in ["custom", "pro", "max5", "max20"]:
            screen_buffer.append("")
            if plan == "custom":
                screen_buffer.append("[bold]📊 Session-Based Dynamic Limits[/bold]")
                screen_buffer.append(
                    "[dim]Based on your historical usage patterns when hitting limits (P90)[/dim]"
                )
                screen_buffer.append(f"[separator]{'─' * 60}[/]")
            else:
                screen_buffer.append("")

            # Phase 2: Threshold Detection rows (D-05, D-06, D-07, D-08, D-09)
            # Phase 4: Suppress threshold rows when web_usage is available (D-17, Pitfall 7)
            threshold_state = kwargs.get("threshold_state")
            _show_threshold_rows = threshold_state is not None and kwargs.get("web_usage") is None
            if _show_threshold_rows:
                screen_buffer.append(f"[separator]{'─' * 60}[/]")

                if threshold_state.status == "calibrating":
                    # D-05: show calibration progress, no false overage warnings (D-06)
                    screen_buffer.append(
                        f"🎯 [value]Token limit:[/]          "
                        f"[dim]Calibrating ({threshold_state.completed_session_count}/10 sessions)[/]"
                    )
                    # D-06: INCLUDED/OVERAGE row suppressed entirely during calibration
                elif threshold_state.status == "auto":
                    # D-07: show P90-inferred value
                    # D-18: append web-unavailable suffix when web data is absent
                    web_unavailable_suffix = (
                        "" if kwargs.get("web_usage") is not None
                        else " (est. — web unavailable)"
                    )
                    screen_buffer.append(
                        f"🎯 [value]Token limit:[/]          "
                        f"[info]{threshold_state.threshold_tokens:,} tokens[/]"
                        f" [dim](P90){web_unavailable_suffix}[/]"
                    )
                    # D-09: status row present when threshold is known
                    tokens_used_val = kwargs.get("tokens_used", tokens_used)
                    if tokens_used_val > threshold_state.threshold_tokens:
                        screen_buffer.append(
                            "🔴 [error]Status:[/]               [error]OVERAGE[/]"
                        )
                    else:
                        screen_buffer.append(
                            "✅ [success]Status:[/]              [success]INCLUDED[/]"
                        )
                else:  # manual
                    # D-08: show manually-configured value
                    # D-18: suffix also shown for manual threshold when web data is absent
                    web_unavailable_suffix = (
                        "" if kwargs.get("web_usage") is not None
                        else " (est. — web unavailable)"
                    )
                    screen_buffer.append(
                        f"🎯 [value]Token limit:[/]          "
                        f"[info]{threshold_state.threshold_tokens:,} tokens[/]"
                        f" [dim](manual){web_unavailable_suffix}[/]"
                    )
                    # D-09: status row present when threshold is known
                    tokens_used_val = kwargs.get("tokens_used", tokens_used)
                    if tokens_used_val > threshold_state.threshold_tokens:
                        screen_buffer.append(
                            "🔴 [error]Status:[/]               [error]OVERAGE[/]"
                        )
                    else:
                        screen_buffer.append(
                            "✅ [success]Status:[/]              [success]INCLUDED[/]"
                        )

            # Phase 3: Pool Dashboard rows (D-12, D-13, D-14; OVGE-01 through OVGE-04, DISP-02)
            pool_state = kwargs.get("pool_state")
            if (
                pool_state is not None
                and threshold_state is not None
                and threshold_state.status != "calibrating"
            ):
                screen_buffer.append(f"[separator]{'─' * 60}[/]")

                # Pool spend row — always shown when threshold is known (D-12, D-13, OVGE-02)
                screen_buffer.append(
                    f"🏦 [value]Pool spent:[/]   est. ${pool_state.pool_spend_usd:.2f} / ${pool_state.pool_size_usd:.2f}"
                )

                # Pool % remaining progress bar (D-14, OVGE-03)
                # CRITICAL: pass pool_pct_SPENT (not remaining) so color escalates as pool depletes.
                # _render_wide_progress_bar: green < 50%, yellow < 80%, red >= 80% of value passed.
                pool_bar = self._render_wide_progress_bar(pool_state.pool_pct_spent)
                pct_remaining = 100.0 - pool_state.pool_pct_spent
                screen_buffer.append(
                    f"   {pool_bar} {pct_remaining:.1f}% remaining"
                )

                # Burn rate + pool exhaustion — OVERAGE state only (D-11, OVGE-04)
                if pool_state.is_overage:
                    # session_cost and elapsed_session_minutes are positional params in scope
                    burn_rate_per_hr = (
                        (session_cost / max(1, elapsed_session_minutes)) * 60
                        if elapsed_session_minutes > 0
                        else 0.0
                    )
                    if burn_rate_per_hr > 0:
                        remaining_hrs = pool_state.pool_remaining_usd / burn_rate_per_hr
                        hours = int(remaining_hrs)
                        mins = int((remaining_hrs - hours) * 60)
                        exhaust_str = f"~{hours}h {mins}m remaining"
                    else:
                        exhaust_str = "—"
                    screen_buffer.append(
                        f"🔥 [value]Pool burn:[/]    est. ${burn_rate_per_hr:.2f}/hr — {exhaust_str}"
                    )

            # Phase 6: Per-project token breakdown (D-14, PROJ-01, PROJ-02, PROJ-03)
            project_breakdown = kwargs.get("project_breakdown")
            if project_breakdown is not None and (project_breakdown.today or project_breakdown.billing_month):
                screen_buffer.append(f"[separator]{'─' * 60}[/]")
                left_lines: list[str] = [f"📂 [value]Today (est.)[/]"]
                right_lines: list[str] = [f"📂 [value]This month (est.)[/]"]
                for name, toks in (project_breakdown.today or []):
                    left_lines.append(f"  [dim]{_col_pad(name, 22)}[/] {_fmt_tokens(toks)}")
                for name, toks in (project_breakdown.billing_month or []):
                    right_lines.append(f"  [dim]{_col_pad(name, 22)}[/] {_fmt_tokens(toks)}")
                while len(left_lines) < len(right_lines):
                    left_lines.append("")
                while len(right_lines) < len(left_lines):
                    right_lines.append("")
                col_width = 36
                for left, right in zip(left_lines, right_lines):
                    screen_buffer.append(f"{_col_pad(left, col_width)}{right}")

            # Phase 4: Web usage rows (D-17, D-18, D-19 from 04-CONTEXT.md)
            web_usage = kwargs.get("web_usage")
            if web_usage is not None:
                screen_buffer.append(f"[separator]{'─' * 60}[/]")

                # D-17: Utilization row with progress bar (reuses _render_wide_progress_bar)
                util_bar = self._render_wide_progress_bar(web_usage.utilization_pct)
                screen_buffer.append(
                    f"🌐 [value]Utilization:[/]   {util_bar} {web_usage.utilization_pct:.1f}%  [dim]via claude.ai[/]"
                )

                # D-17: Resets In row — countdown to reset_at (UTC)
                now_utc = datetime.now(dt_timezone.utc)
                delta = web_usage.reset_at - now_utc
                total_secs = max(0, int(delta.total_seconds()))
                hours, rem = divmod(total_secs, 3600)
                mins = rem // 60
                screen_buffer.append(
                    f"⏱  [value]Resets in:[/]     {hours}h {mins}m"
                )

                # D-19: Last web sync footer (shown after first successful fetch)
                last_sync = kwargs.get("last_web_sync")
                if last_sync:
                    screen_buffer.append(
                        f"🔄 [dim]Last web sync: {last_sync.astimezone().strftime('%H:%M:%S')}[/]"
                    )

                # D-08: Model Distribution, Burn Rate, Cost Rate moved here (Phase 6)
                if per_model_stats:
                    model_bar = self.model_usage.render(per_model_stats)
                    screen_buffer.append(f"🤖 [value]Model Distribution:[/]   {model_bar}")
                else:
                    model_bar = self.model_usage.render({})
                    screen_buffer.append(f"🤖 [value]Model Distribution:[/]   {model_bar}")
                screen_buffer.append(f"[separator]{'─' * 60}[/]")

                velocity_emoji = VelocityIndicator.get_velocity_emoji(burn_rate)
                screen_buffer.append(
                    f"🔥 [value]Burn Rate:[/]              [warning]{burn_rate:.1f}[/] [dim]tokens/min[/] {velocity_emoji}"
                )

                cost_per_min = (
                    session_cost / max(1, elapsed_session_minutes)
                    if elapsed_session_minutes > 0
                    else 0
                )
                cost_per_min_display = CostIndicator.render(cost_per_min)
                screen_buffer.append(
                    f"💲 [value]Cost Rate:[/]              {cost_per_min_display} [dim]$/min[/]"
                )
        else:
            cost_display = CostIndicator.render(session_cost)
            cost_per_min = (
                session_cost / max(1, elapsed_session_minutes)
                if elapsed_session_minutes > 0
                else 0
            )
            cost_per_min_display = CostIndicator.render(cost_per_min)
            screen_buffer.append(f"💲 [value]Session Cost:[/]   {cost_display}")
            screen_buffer.append(
                f"💲 [value]Cost Rate:[/]      {cost_per_min_display} [dim]$/min[/]"
            )
            screen_buffer.append("")

            token_bar = self.token_progress.render(usage_percentage)
            screen_buffer.append(f"📊 [value]Token Usage:[/]    {token_bar}")
            screen_buffer.append("")

            screen_buffer.append(
                f"🎯 [value]Tokens:[/]         [value]{tokens_used:,}[/] / [dim]~{token_limit:,}[/] ([info]{tokens_left:,} left[/])"
            )

            velocity_emoji = VelocityIndicator.get_velocity_emoji(burn_rate)
            screen_buffer.append(
                f"🔥 [value]Burn Rate:[/]      [warning]{burn_rate:.1f}[/] [dim]tokens/min[/] {velocity_emoji}"
            )

            screen_buffer.append(
                f"📨 [value]Sent Messages:[/]  [info]{sent_messages}[/] [dim]messages[/]"
            )

            if per_model_stats:
                model_bar = self.model_usage.render(per_model_stats)
                screen_buffer.append(f"🤖 [value]Model Usage:[/]    {model_bar}")

            screen_buffer.append("")

            time_bar = self.time_progress.render(
                elapsed_session_minutes, total_session_minutes
            )
            screen_buffer.append(f"⏱️  [value]Time to Reset:[/]  {time_bar}")
            screen_buffer.append("")

        screen_buffer.append("")
        screen_buffer.append("🔮 [value]Predictions:[/]")
        screen_buffer.append(
            f"   [info]Tokens will run out:[/] [warning]{predicted_end_str}[/]"
        )
        screen_buffer.append(
            f"   [info]Limit resets at:[/]     [success]{reset_time_str}[/]"
        )
        screen_buffer.append("")

        self._add_notifications(
            screen_buffer,
            show_switch_notification,
            show_exceed_notification,
            show_tokens_will_run_out,
            original_limit,
            token_limit,
        )

        screen_buffer.append(
            f"⏰ [dim]{current_time_str}[/] 📝 [success]Active session[/] | [dim]Ctrl+C to exit[/] 🟢"
        )

        return screen_buffer

    def _add_notifications(
        self,
        screen_buffer: list[str],
        show_switch_notification: bool,
        show_exceed_notification: bool,
        show_tokens_will_run_out: bool,
        original_limit: int,
        token_limit: int,
    ) -> None:
        """Add notification messages to screen buffer.

        Args:
            screen_buffer: Screen buffer to append to
            show_switch_notification: Show plan switch notification
            show_exceed_notification: Show exceed limit notification
            show_tokens_will_run_out: Show token depletion warning
            original_limit: Original plan limit
            token_limit: Current token limit
        """
        notifications_added = False

        if show_switch_notification and token_limit > original_limit:
            screen_buffer.append(
                f"🔄 [warning]Token limit exceeded ({token_limit:,} tokens)[/]"
            )
            notifications_added = True

        if show_exceed_notification:
            screen_buffer.append(
                "⚠️  [error]You have exceeded the maximum cost limit![/]"
            )
            notifications_added = True

        if show_tokens_will_run_out:
            screen_buffer.append(
                "⏰ [warning]Cost limit will be exceeded before reset![/]"
            )
            notifications_added = True

        if notifications_added:
            screen_buffer.append("")

    def format_no_active_session_screen(
        self,
        plan: str,
        timezone: str,
        token_limit: int,
        current_time: Optional[datetime] = None,
        args: Optional[Any] = None,
    ) -> list[str]:
        """Format screen for no active session state.

        Args:
            plan: Current plan name
            timezone: Display timezone
            token_limit: Token limit for the plan
            current_time: Current datetime
            args: Command line arguments

        Returns:
            List of formatted screen lines
        """

        screen_buffer = []

        header_manager = HeaderManager()
        screen_buffer.extend(header_manager.create_header(plan, timezone))

        empty_token_bar = self.token_progress.render(0.0)
        screen_buffer.append(f"📊 [value]Token Usage:[/]    {empty_token_bar}")
        screen_buffer.append("")

        screen_buffer.append(
            f"🎯 [value]Tokens:[/]         [value]0[/] / [dim]~{token_limit:,}[/] ([info]0 left[/])"
        )
        screen_buffer.append(
            "🔥 [value]Burn Rate:[/]      [warning]0.0[/] [dim]tokens/min[/]"
        )
        screen_buffer.append(
            "💲 [value]Cost Rate:[/]      [cost.low]$0.00[/] [dim]$/min[/]"
        )
        screen_buffer.append("📨 [value]Sent Messages:[/]  [info]0[/] [dim]messages[/]")
        screen_buffer.append("")

        if current_time and args:
            try:
                display_tz = pytz.timezone(args.timezone)
                current_time_display = current_time.astimezone(display_tz)
                current_time_str = format_display_time(
                    current_time_display,
                    get_time_format_preference(args),
                    include_seconds=True,
                )
                screen_buffer.append(
                    f"⏰ [dim]{current_time_str}[/] 📝 [info]No active session[/] | [dim]Ctrl+C to exit[/] 🟨"
                )
            except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
                screen_buffer.append(
                    "⏰ [dim]--:--:--[/] 📝 [info]No active session[/] | [dim]Ctrl+C to exit[/] 🟨"
                )
        else:
            screen_buffer.append(
                "⏰ [dim]--:--:--[/] 📝 [info]No active session[/] | [dim]Ctrl+C to exit[/] 🟨"
            )

        return screen_buffer
