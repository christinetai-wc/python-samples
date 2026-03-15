"""Async Notion API client for querying and creating/updating pages."""

from __future__ import annotations

import os
from datetime import datetime

import httpx
from dotenv import load_dotenv

from config import NOTION_DATABASE_ID_DEFAULT
from models import CourseEvent, DiffItem, NotionRecord

load_dotenv()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Wrapper around Notion REST API."""

    def __init__(self) -> None:
        self.token = os.getenv("NOTION_TOKEN", "")
        self.database_id = os.getenv("NOTION_DATABASE_ID", NOTION_DATABASE_ID_DEFAULT)
        if not self.token:
            raise ValueError("NOTION_TOKEN not set in .env")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def fetch_records_in_range(
        self, start: datetime, end: datetime
    ) -> list[NotionRecord]:
        """Query Notion database for records where Start time is within [start, end]."""
        body = {
            "filter": {
                "and": [
                    {
                        "property": "Start time",
                        "date": {"on_or_after": start.isoformat()},
                    },
                    {
                        "property": "Start time",
                        "date": {"on_or_before": end.isoformat()},
                    },
                ]
            },
            "page_size": 100,
        }
        return await self._query_database(body)

    async def fetch_records_by_prefix(self, prefix: str) -> list[NotionRecord]:
        """Query all records whose Task Name contains the prefix (for numbering)."""
        body = {
            "filter": {
                "property": "Task Name",
                "title": {"contains": prefix},
            },
            "page_size": 100,
        }
        records: list[NotionRecord] = []
        # Paginate to get all records
        has_more = True
        start_cursor = None
        while has_more:
            if start_cursor:
                body["start_cursor"] = start_cursor
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{NOTION_API}/databases/{self.database_id}/query",
                    headers=self.headers,
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
            records.extend(self._parse_results(data.get("results", [])))
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
        return records

    async def fetch_all_records(
        self, start: datetime, end: datetime
    ) -> list[NotionRecord]:
        """Fetch records in the date range for comparison."""
        return await self.fetch_records_in_range(start, end)

    async def create_page(self, event: CourseEvent) -> str:
        """Create a new Notion page. Returns the page ID."""
        properties: dict = {
            "Task Name": {"title": [{"text": {"content": event.task_name}}]},
            "Task Category": {"multi_select": [{"name": event.category}]},
            "Start time": {"date": {"start": event.start_time.isoformat()}},
            "hours": {"number": event.hours},
            "Done": {"checkbox": False},
        }
        if event.cost is not None:
            properties["Cost"] = {"number": event.cost}
        if event.description:
            properties["Task Description"] = {
                "rich_text": [{"text": {"content": event.description}}]
            }

        body = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{NOTION_API}/pages",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def update_page_time(self, page_id: str, new_start: datetime) -> None:
        """Update the Start time of an existing Notion page."""
        body = {
            "properties": {
                "Start time": {"date": {"start": new_start.isoformat()}},
            }
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{NOTION_API}/pages/{page_id}",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()

    async def update_page_title(self, page_id: str, new_title: str) -> None:
        """Update the Title of an existing Notion page."""
        body = {
            "properties": {
                "Task Name": {"title": [{"text": {"content": new_title}}]},
            }
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{NOTION_API}/pages/{page_id}",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()

    async def execute_actions(self, actions: list[DiffItem]) -> list[str]:
        """Execute confirmed add/update actions. Returns list of descriptions."""
        results: list[str] = []
        for item in actions:
            if item.action.value == "add" and item.event:
                page_id = await self.create_page(item.event)
                results.append(f"新增 {item.event.task_name}")
            elif item.action.value == "fixed_missing" and item.event:
                page_id = await self.create_page(item.event)
                results.append(f"新增 {item.event.task_name}")
            elif item.action.value == "update" and item.event and item.notion_record:
                await self.update_page_time(
                    item.notion_record.page_id, item.event.start_time
                )
                results.append(f"更新 {item.event.task_name} 時間")
            elif item.action.value == "update_title" and item.event and item.notion_record:
                await self.update_page_title(
                    item.notion_record.page_id, item.event.task_name
                )
                results.append(f"更新標題 {item.notion_record.task_name} → {item.event.task_name}")
        return results

    async def _query_database(self, body: dict) -> list[NotionRecord]:
        """Execute a database query and parse results."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{NOTION_API}/databases/{self.database_id}/query",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        return self._parse_results(data.get("results", []))

    def _parse_results(self, results: list[dict]) -> list[NotionRecord]:
        """Parse Notion API results into NotionRecord objects."""
        records: list[NotionRecord] = []
        for page in results:
            props = page.get("properties", {})
            records.append(
                NotionRecord(
                    page_id=page["id"],
                    task_name=self._get_title(props.get("Task Name", {})),
                    category=self._get_multi_select(props.get("Task Category", {})),
                    start_time=self._get_datetime(props.get("Start time", {})),
                    hours=self._get_number(props.get("hours", {})),
                    cost=self._get_number(props.get("Cost", {})),
                    done=self._get_checkbox(props.get("Done", {})),
                    description=self._get_rich_text(
                        props.get("Task Description", {})
                    ),
                )
            )
        return records

    @staticmethod
    def _get_title(prop: dict) -> str:
        title_arr = prop.get("title", [])
        return title_arr[0]["plain_text"] if title_arr else ""

    @staticmethod
    def _get_select(prop: dict) -> str:
        sel = prop.get("select")
        return sel["name"] if sel else ""

    @staticmethod
    def _get_multi_select(prop: dict) -> str:
        items = prop.get("multi_select", [])
        return items[0]["name"] if items else ""

    @staticmethod
    def _get_datetime(prop: dict) -> datetime | None:
        date_obj = prop.get("date")
        if not date_obj or not date_obj.get("start"):
            return None
        return datetime.fromisoformat(date_obj["start"])

    @staticmethod
    def _get_number(prop: dict) -> float | None:
        val = prop.get("number")
        return val if val is not None else None

    @staticmethod
    def _get_checkbox(prop: dict) -> bool:
        return prop.get("checkbox", False)

    @staticmethod
    def _get_rich_text(prop: dict) -> str | None:
        arr = prop.get("rich_text", [])
        return arr[0]["plain_text"] if arr else None
