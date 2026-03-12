"""Fixed-schedule date calculator for courses without Google Calendar."""

from __future__ import annotations

from datetime import datetime, timedelta

from config import TPE, FixedCourseConfig
from models import CourseEvent


def calculate_fixed_dates(
    courses: list[FixedCourseConfig],
    start: datetime,
    end: datetime,
) -> list[CourseEvent]:
    """Calculate all expected class dates within [start, end] for fixed-schedule courses."""
    events: list[CourseEvent] = []
    for cfg in courses:
        current = start
        while current <= end:
            if current.weekday() in cfg.weekdays:
                start_time = current.replace(
                    hour=cfg.start_hour,
                    minute=cfg.start_minute,
                    second=0,
                    microsecond=0,
                    tzinfo=TPE,
                )
                events.append(
                    CourseEvent(
                        course_key=cfg.key,
                        task_name_prefix=cfg.task_name_prefix,
                        task_name="",  # filled by numbering
                        category=cfg.category,
                        start_time=start_time,
                        hours=cfg.hours,
                        cost=cfg.cost,
                        description=cfg.description_template,
                        source="fixed",
                    )
                )
            current += timedelta(days=1)
    return events
