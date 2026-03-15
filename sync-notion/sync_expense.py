#!/usr/bin/env python3
"""
sync_expense.py — 將已發生的課程費用同步到 FOCUS支出 資料庫

Usage:
    python sync_expense.py              # 從預設起始日期開始同步
    python sync_expense.py 2026-01-01   # 指定起始日期
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

from config import TPE

load_dotenv()
console = Console()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# 上課時間（來源）
COURSE_DB_ID = os.getenv("NOTION_DATABASE_ID", "202ecea7a5c7800abd51000b1008a72e")
# FOCUS支出（目標）
EXPENSE_DB_ID = "255ecea7a5c7815fa752d6f7918eefb6"
# 中國信託帳戶
BANK_ACCOUNT_PAGE_ID = "255ecea7-a5c7-819b-b570-c1e5c48d7db3"
# 預設起始日期
DEFAULT_SINCE = "2026-03-01"


@dataclass
class CourseRecord:
    """從上課時間資料庫讀取的課程紀錄。"""
    page_id: str
    task_name: str
    start_date: str  # YYYY-MM-DD
    cost: int
    description: str


@dataclass
class ExpenseRecord:
    """從 FOCUS支出 資料庫讀取的既有支出紀錄。"""
    page_id: str
    item_name: str
    date: str  # YYYY-MM-DD


def _headers() -> dict:
    token = os.getenv("NOTION_TOKEN", "")
    if not token:
        raise ValueError("NOTION_TOKEN not set in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


async def _query_all(db_id: str, body: dict) -> list[dict]:
    """Paginated query for a Notion database."""
    headers = _headers()
    results: list[dict] = []
    has_more = True
    start_cursor = None
    async with httpx.AsyncClient(timeout=30) as client:
        while has_more:
            if start_cursor:
                body["start_cursor"] = start_cursor
            resp = await client.post(
                f"{NOTION_API}/databases/{db_id}/query",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results", []))
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
    return results


async def fetch_past_courses(since: str) -> list[CourseRecord]:
    """查詢上課時間資料庫中 since <= 日期 < 今天 且 cost > 0 的紀錄。"""
    today = datetime.now(TPE).strftime("%Y-%m-%d")
    body = {
        "filter": {
            "and": [
                {"property": "Start time", "date": {"on_or_after": since}},
                {"property": "Start time", "date": {"on_or_before": today}},
                {"property": "Cost", "number": {"greater_than": 0}},
            ]
        },
        "sorts": [{"property": "Start time", "direction": "ascending"}],
        "page_size": 100,
    }
    pages = await _query_all(COURSE_DB_ID, body)
    records: list[CourseRecord] = []
    for page in pages:
        props = page.get("properties", {})
        # task name
        title_arr = props.get("Task Name", {}).get("title", [])
        task_name = title_arr[0]["plain_text"] if title_arr else ""
        # start date
        date_obj = props.get("Start time", {}).get("date")
        if not date_obj or not date_obj.get("start"):
            continue
        start_raw = date_obj["start"]
        start_date = start_raw[:10]  # YYYY-MM-DD
        # cost
        cost_val = props.get("Cost", {}).get("number")
        if not cost_val or cost_val <= 0:
            continue
        # description
        desc_arr = props.get("Task Description", {}).get("rich_text", [])
        description = desc_arr[0]["plain_text"] if desc_arr else ""

        records.append(CourseRecord(
            page_id=page["id"],
            task_name=task_name,
            start_date=start_date,
            cost=int(cost_val),
            description=description,
        ))
    return records


async def fetch_existing_expenses() -> list[ExpenseRecord]:
    """查詢 FOCUS支出 中種類=教育Neo 的所有紀錄。"""
    body = {
        "filter": {
            "property": "種類",
            "select": {"equals": "教育Neo"},
        },
        "page_size": 100,
    }
    pages = await _query_all(EXPENSE_DB_ID, body)
    records: list[ExpenseRecord] = []
    for page in pages:
        props = page.get("properties", {})
        # item name
        title_arr = props.get("項目", {}).get("title", [])
        item_name = title_arr[0]["plain_text"] if title_arr else ""
        # date
        date_obj = props.get("日期", {}).get("date")
        date_str = date_obj["start"][:10] if date_obj and date_obj.get("start") else ""

        records.append(ExpenseRecord(
            page_id=page["id"],
            item_name=item_name,
            date=date_str,
        ))
    return records


def compute_new_expenses(
    courses: list[CourseRecord],
    existing: list[ExpenseRecord],
) -> list[CourseRecord]:
    """比對找出尚未同步的課程費用。"""
    existing_keys = {(e.item_name, e.date) for e in existing}
    return [c for c in courses if (c.task_name, c.start_date) not in existing_keys]


async def create_expense(course: CourseRecord) -> str:
    """在 FOCUS支出 建立一筆支出紀錄。"""
    headers = _headers()
    properties: dict = {
        "項目": {"title": [{"text": {"content": course.task_name}}]},
        "花費": {"number": course.cost},
        "種類": {"select": {"name": "教育Neo"}},
        "日期": {"date": {"start": course.start_date}},
        "對應帳戶": {"relation": [{"id": BANK_ACCOUNT_PAGE_ID}]},
    }
    if course.description:
        properties["花費理由"] = {
            "rich_text": [{"text": {"content": course.description}}]
        }
    body = {
        "parent": {"database_id": EXPENSE_DB_ID},
        "properties": properties,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{NOTION_API}/pages",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()["id"]


def display_pending(new_items: list[CourseRecord]) -> None:
    """顯示待同步的項目清單。"""
    console.print(f"\n[cyan]➕ 待新增到 FOCUS支出（共 {len(new_items)} 筆）：[/cyan]")
    total = 0
    for c in new_items:
        desc = f"  ({c.description})" if c.description else ""
        console.print(f"  - {c.task_name:<20s} {c.start_date}  ${c.cost:,}{desc}")
        total += c.cost
    console.print(f"\n  [bold]合計：${total:,}[/bold]\n")


def confirm() -> bool:
    """互動確認。"""
    choice = Prompt.ask("確認同步到 FOCUS支出？", choices=["y", "n"], default="y")
    return choice == "y"


def parse_since() -> str:
    """從命令列參數取得起始日期，預設 DEFAULT_SINCE。"""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # 簡單驗證格式
        try:
            datetime.strptime(arg, "%Y-%m-%d")
            return arg
        except ValueError:
            console.print(f"[red]日期格式錯誤：{arg}（應為 YYYY-MM-DD）[/red]")
            raise SystemExit(1)
    return DEFAULT_SINCE


async def main() -> None:
    since = parse_since()
    console.print(f"[bold]🔄 同步課程費用 → FOCUS支出[/bold]（自 {since} 起）\n")

    console.print("[dim]查詢上課時間 + FOCUS支出...[/dim]")
    courses, existing = await asyncio.gather(
        fetch_past_courses(since),
        fetch_existing_expenses(),
    )
    console.print(f"  已發生且有費用的課程：{len(courses)} 筆")
    console.print(f"  FOCUS支出（教育Neo）：{len(existing)} 筆\n")

    new_items = compute_new_expenses(courses, existing)

    if not new_items:
        console.print("[green]✨ 所有課程費用皆已同步，無需更新。[/green]")
        return

    display_pending(new_items)

    if not confirm():
        console.print("[dim]已取消。[/dim]")
        return

    console.print("\n[dim]寫入中...[/dim]")
    for c in new_items:
        await create_expense(c)
        console.print(f"  ✓ {c.task_name} {c.start_date}")

    console.print(f"\n[green bold]✅ 完成！共新增 {len(new_items)} 筆支出。[/green bold]")


if __name__ == "__main__":
    asyncio.run(main())
