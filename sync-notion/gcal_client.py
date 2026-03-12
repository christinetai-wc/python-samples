"""Async Google Calendar API client."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import aiohttp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import GCAL_SCOPES, GCalCourseConfig
from models import CourseEvent

PROJECT_DIR = Path(__file__).parent
TOKEN_PATH = PROJECT_DIR / "token.json"
CLIENT_SECRET_PATH = PROJECT_DIR / "client_secret.json"


def authenticate() -> Credentials:
    """Run OAuth2 flow or load existing token."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), GCAL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"找不到 {CLIENT_SECRET_PATH}\n"
                    "請從 Google Cloud Console 下載 OAuth 2.0 Desktop credentials，"
                    "存為 client_secret.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), GCAL_SCOPES
            )
            # Use a fixed port so the redirect URL is predictable
            creds = flow.run_local_server(
                port=8090,
                open_browser=False,
                prompt="consent",
            )
            print("  請在瀏覽器打開上方網址完成授權。")

        TOKEN_PATH.write_text(creds.to_json())

    return creds


class GCalClient:
    """Fetches events from multiple Google Calendars in parallel."""

    def __init__(self) -> None:
        self._creds = authenticate()

    @property
    def _access_token(self) -> str:
        if not self._creds.valid:
            self._creds.refresh(Request())
        return self._creds.token

    async def fetch_all_courses(
        self,
        courses: list[GCalCourseConfig],
        start: datetime,
        end: datetime,
    ) -> list[CourseEvent]:
        """Query all calendars in parallel, deduplicating shared calendar IDs."""
        # Group configs by calendar_id
        cal_groups: dict[str, list[GCalCourseConfig]] = {}
        for c in courses:
            cal_groups.setdefault(c.calendar_id, []).append(c)

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_calendar(session, cal_id, cfgs, start, end)
                for cal_id, cfgs in cal_groups.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        events: list[CourseEvent] = []
        for result in results:
            if isinstance(result, BaseException):
                print(f"  [WARN] Calendar query failed: {result}")
                continue
            events.extend(result)
        return events

    async def _fetch_calendar(
        self,
        session: aiohttp.ClientSession,
        calendar_id: str,
        configs: list[GCalCourseConfig],
        start: datetime,
        end: datetime,
    ) -> list[CourseEvent]:
        """Fetch events from one calendar, filter and map to CourseEvent."""
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        params = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": "Asia/Taipei",
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"GCal API {resp.status}: {text[:200]}")
            data = await resp.json()

        events: list[CourseEvent] = []
        for item in data.get("items", []):
            summary = (item.get("summary") or "").strip()
            for cfg in configs:
                if cfg.event_filter in summary:
                    events.append(self._map_event(item, cfg))
        return events

    def _map_event(self, gcal_item: dict, cfg: GCalCourseConfig) -> CourseEvent:
        """Convert a GCal event dict to a CourseEvent."""
        start_str = gcal_item["start"].get("dateTime", gcal_item["start"].get("date"))
        end_str = gcal_item["end"].get("dateTime", gcal_item["end"].get("date"))
        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)

        hours = cfg.default_hours or (end_dt - start_dt).total_seconds() / 3600

        return CourseEvent(
            course_key=cfg.key,
            task_name_prefix=cfg.task_name_prefix,
            task_name="",  # filled later by numbering
            category=cfg.category,
            start_time=start_dt,
            end_time=end_dt,
            hours=hours,
            cost=cfg.cost,
            description=cfg.description_template,
            source="gcal",
            gcal_event_id=gcal_item.get("id"),
        )
