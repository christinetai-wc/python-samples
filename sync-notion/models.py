"""Data models for sync-notion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DiffAction(Enum):
    SKIP = "skip"
    ADD = "add"
    UPDATE_TIME = "update"
    GCAL_CANCELLED = "gcal_cancelled"
    FIXED_MISSING = "fixed_missing"


@dataclass
class CourseEvent:
    """A course occurrence from GCal or fixed schedule."""

    course_key: str
    task_name_prefix: str
    task_name: str  # filled after numbering, e.g. "自然課 (5)"
    category: str
    start_time: datetime  # TPE timezone-aware
    hours: float
    cost: int | None
    description: str
    source: str  # "gcal" or "fixed"
    end_time: datetime | None = None
    gcal_event_id: str | None = None


@dataclass
class NotionRecord:
    """An existing record from the Notion database."""

    page_id: str
    task_name: str
    category: str
    start_time: datetime | None
    hours: float | None
    cost: int | None
    done: bool
    description: str | None = None


@dataclass
class DiffItem:
    """A single diff entry."""

    action: DiffAction
    event: CourseEvent | None = None
    notion_record: NotionRecord | None = None
    detail: str = ""

    @property
    def sort_key(self) -> datetime:
        if self.event and self.event.start_time:
            return self.event.start_time
        if self.notion_record and self.notion_record.start_time:
            return self.notion_record.start_time
        return datetime.min


@dataclass
class DiffResult:
    """Complete diff between sources and Notion."""

    skipped: list[DiffItem] = field(default_factory=list)
    to_add: list[DiffItem] = field(default_factory=list)
    time_changed: list[DiffItem] = field(default_factory=list)
    gcal_cancelled: list[DiffItem] = field(default_factory=list)
    fixed_missing: list[DiffItem] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.to_add
            or self.time_changed
            or self.gcal_cancelled
            or self.fixed_missing
        )
