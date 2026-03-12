#!/usr/bin/env python3
"""
sync_cal.py — Neo 自學課程行事曆 × Notion 同步工具

Usage:
    python sync_cal.py              # 預設：未來 2 週
    python sync_cal.py today        # 只看今天
    python sync_cal.py 2weeks       # 未來 14 天
    python sync_cal.py --auth       # 首次 Google OAuth 授權
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from rich.console import Console

from config import GCAL_COURSES, FIXED_COURSES, TPE
from display import confirm_actions, print_diff_report
from index_updater import update_index

load_dotenv()
console = Console()


def parse_args() -> str:
    """Return 'today', '2weeks', or '--auth'."""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("today", "2weeks", "--auth"):
            return arg
    return "2weeks"


def compute_date_range(mode: str) -> tuple[datetime, datetime]:
    """Return (start, end) in TPE timezone."""
    now = datetime.now(TPE)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if mode == "today":
        end = start.replace(hour=23, minute=59, second=59)
    else:
        end = (start + timedelta(days=14)).replace(hour=23, minute=59, second=59)
    return start, end


async def main() -> None:
    mode = parse_args()

    # Handle --auth: just run OAuth flow and exit
    if mode == "--auth":
        from gcal_client import authenticate

        console.print("[bold]Google Calendar OAuth 授權...[/bold]")
        authenticate()
        console.print("[green]✅ 授權完成！token.json 已儲存。[/green]")
        return

    start, end = compute_date_range(mode)
    period = "今天" if mode == "today" else "未來2週"
    console.print(
        f"[bold]🔄 同步課程（{period}）[/bold] "
        f"{start.strftime('%m/%d')}–{end.strftime('%m/%d')}\n"
    )

    # Import here to avoid import errors if credentials aren't set up yet
    from gcal_client import GCalClient
    from notion_client import NotionClient
    from scheduler import calculate_fixed_dates
    from numbering import resolve_numbering
    from differ import compute_diff

    gcal = GCalClient()
    notion = NotionClient()

    # Step 1+2: Parallel fetch from GCal + Notion
    console.print("[dim]查詢 Google Calendar + Notion...[/dim]")
    gcal_events, notion_records = await asyncio.gather(
        gcal.fetch_all_courses(GCAL_COURSES, start, end),
        notion.fetch_all_records(start, end),
    )
    console.print(
        f"  GCal: {len(gcal_events)} 筆事件, "
        f"Notion: {len(notion_records)} 筆紀錄"
    )

    # Step 3: Calculate fixed-schedule expected dates
    fixed_events = calculate_fixed_dates(FIXED_COURSES, start, end)
    console.print(f"  固定排課: {len(fixed_events)} 筆預期\n")

    # Step 4: Resolve numbering
    await resolve_numbering(gcal_events, fixed_events, notion, notion_records)

    # Step 5: Compute diff
    diff = compute_diff(gcal_events, fixed_events, notion_records, start, end)

    # Step 6: Display diff
    if diff.is_empty():
        print_diff_report(diff, mode, "本期間 Notion 與課程表資料一致，無需更新 ✨")
        return

    print_diff_report(diff, mode)

    # Step 7: Confirm and execute
    actions = confirm_actions(diff)
    if not actions:
        return

    console.print("\n[dim]執行中...[/dim]")
    descriptions = await notion.execute_actions(actions)

    # Step 8: Update index file
    if descriptions:
        update_index(descriptions)

    console.print(f"\n[green bold]✅ 同步完成！共 {len(descriptions)} 項變更。[/green bold]")


if __name__ == "__main__":
    asyncio.run(main())
