"""Colorful terminal output using rich."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.prompt import Prompt

from models import DiffItem, DiffResult

console = Console()
WEEKDAYS_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def _fmt_date(dt: datetime) -> str:
    """Format date as '3/11 週三'."""
    wd = WEEKDAYS_ZH[dt.weekday()]
    return f"{dt.month}/{dt.day} {wd}"


def _fmt_time_range(ev) -> str:
    """Format time range like '14:00–16:00'."""
    start = ev.start_time.strftime("%H:%M")
    if ev.end_time:
        end = ev.end_time.strftime("%H:%M")
        return f"{start}–{end}"
    # Calculate end from hours
    from datetime import timedelta

    end_dt = ev.start_time + timedelta(hours=ev.hours)
    return f"{start}–{end_dt.strftime('%H:%M')}"


def print_diff_report(diff: DiffResult, mode: str, msg: str = "") -> None:
    """Print the full diff report to terminal."""
    period = "今天" if mode == "today" else "未來2週"
    console.print(f"\n[bold]📋 syncCal 結果（{period}）[/bold]\n")

    if msg:
        console.print(f"  {msg}\n")
        return

    # ✅ Skipped
    if diff.skipped:
        console.print("[green]✅ 已存在，略過：[/green]")
        for item in diff.skipped:
            ev = item.event
            if ev:
                console.print(
                    f"  - {ev.task_name:<20s} {_fmt_date(ev.start_time)} "
                    f"{ev.start_time.strftime('%H:%M')}"
                )
        console.print()

    # ➕ To add (GCal)
    if diff.to_add:
        console.print("[cyan]➕ 待新增（確認後新增）：[/cyan]")
        for item in diff.to_add:
            ev = item.event
            if ev:
                cost_str = f"  Cost:{ev.cost}" if ev.cost else ""
                console.print(
                    f"  - {ev.task_name:<20s} {_fmt_date(ev.start_time)} "
                    f"{_fmt_time_range(ev)}{cost_str}"
                )
        console.print()

    # ⚠️ Time changed
    if diff.time_changed:
        console.print("[yellow]⚠️  時間有變動（確認後更新）：[/yellow]")
        for item in diff.time_changed:
            ev = item.event
            if ev:
                console.print(f"  - {ev.task_name:<20s} {item.detail}")
        console.print()

    # ❓ GCal cancelled
    if diff.gcal_cancelled:
        console.print("[red]❓ GCal 已無此課，請確認：[/red]")
        for item in diff.gcal_cancelled:
            rec = item.notion_record
            if rec and rec.start_time:
                console.print(
                    f"  - {rec.task_name:<20s} {_fmt_date(rec.start_time)}（{item.detail}）"
                )
        console.print()

    # ❓ Fixed missing
    if diff.fixed_missing:
        console.print("[magenta]❓ 無 GCal 課程缺漏，確認是否新增？[/magenta]")
        for item in diff.fixed_missing:
            ev = item.event
            if ev:
                cost_str = f"  Cost:{ev.cost}" if ev.cost else ""
                console.print(
                    f"  - {ev.task_name:<20s} {_fmt_date(ev.start_time)} "
                    f"{_fmt_time_range(ev)}{cost_str}"
                )
        console.print()


def confirm_actions(diff: DiffResult) -> list[DiffItem] | None:
    """
    Interactive confirmation.

    Returns list of confirmed actions, or None to abort.
    """
    actionable = diff.to_add + diff.time_changed + diff.fixed_missing
    if not actionable:
        console.print("[dim]沒有需要執行的動作。[/dim]")
        return None

    console.print("[bold]確認執行以上變更嗎？[/bold]")
    console.print("  [dim]y = 全部確認 / n = 取消 / add = 只新增 / update = 只更新時間 / fixed = 只補固定課[/dim]")

    choice = Prompt.ask("選擇", default="y").strip().lower()

    if choice in ("n", "no"):
        console.print("[dim]已取消。[/dim]")
        return None
    elif choice in ("y", "yes"):
        return actionable
    elif choice == "add":
        return diff.to_add
    elif choice == "update":
        return diff.time_changed
    elif choice == "fixed":
        return diff.fixed_missing
    else:
        console.print(f"[dim]未知選項 '{choice}'，已取消。[/dim]")
        return None
