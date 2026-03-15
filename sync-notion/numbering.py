"""Sequential numbering logic for courses with (N)."""

from __future__ import annotations

import re
from datetime import datetime

from config import GCAL_COURSES, FIXED_COURSES, TPE
from models import CourseEvent, NotionRecord


def _get_config(course_key: str):
    """Look up the course config by key."""
    for cfg in GCAL_COURSES:
        if cfg.key == course_key:
            return cfg
    for cfg in FIXED_COURSES:
        if cfg.key == course_key:
            return cfg
    return None


def _find_max_number(prefix: str, records: list[NotionRecord]) -> int:
    """Find the maximum (N) in existing Notion records for this prefix."""
    pattern = re.compile(rf"^{re.escape(prefix)}\s*\((\d+)\)$")
    max_n = 0
    for rec in records:
        m = pattern.match(rec.task_name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n


def _find_latest_number(prefix: str, records: list[NotionRecord]) -> int:
    """Find the number (N) of the chronologically last record for this prefix."""
    # Helper to sort safely
    def _sort_key(r: NotionRecord):
        dt = r.start_time
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=TPE)
        return dt or datetime.min.replace(tzinfo=TPE)

    sorted_recs = sorted(records, key=_sort_key, reverse=True)
    pattern = re.compile(rf"^{re.escape(prefix)}\s*\((\d+)\)$")
    for rec in sorted_recs:
        m = pattern.match(rec.task_name)
        if m:
            return int(m.group(1))
    return 0

def _find_matching_record(
    prefix: str, date: datetime, records: list[NotionRecord]
) -> NotionRecord | None:
    """Find an existing Notion record matching prefix + same date (TPE)."""
    for rec in records:
        if rec.start_time and rec.start_time.date() == date.date():
            if prefix in rec.task_name:
                return rec
    return None


async def resolve_numbering(
    gcal_events: list[CourseEvent],
    fixed_events: list[CourseEvent],
    notion_client,
    range_records: list[NotionRecord],
) -> None:
    """
    Assign task_name to all events.
    For courses with (N), query Notion for max N and assign next numbers.
    For courses without numbering, set task_name = prefix.
    Modifies events in-place.
    """
    all_events = gcal_events + fixed_events

    # Group by course_key
    by_key: dict[str, list[CourseEvent]] = {}
    for ev in all_events:
        by_key.setdefault(ev.course_key, []).append(ev)

    for course_key, events in by_key.items():
        cfg = _get_config(course_key)
        if not cfg:
            continue

        if not cfg.has_numbering:
            # No numbering — task_name = prefix
            for ev in events:
                ev.task_name = ev.task_name_prefix
            continue

        # Fetch ALL records for this prefix to find max number
        all_records = await notion_client.fetch_records_by_prefix(
            cfg.task_name_prefix
        )

        # Sort events chronologically first to find the cutoff time
        events_sorted = sorted(events, key=lambda e: e.start_time)
        if not events_sorted:
            continue

        # Calculate max_n only from records strictly BEFORE the first event in this sync batch
        cutoff_time = events_sorted[0].start_time

        def _ensure_aware(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=TPE)
            return dt

        past_records = [r for r in all_records if r.start_time and _ensure_aware(r.start_time) < cutoff_time]

        # For courses that reset per period, compute the within-period number
        if cfg.numbering_resets:
            # Use the latest record's number (sequence), not the global max (value)
            last_n = _find_latest_number(cfg.task_name_prefix, past_records)
            if cfg.period_size:
                next_n = last_n + 1 if last_n < cfg.period_size else 1
            else:
                next_n = last_n + 1
        else:
            # Continuous numbering
            max_n = _find_max_number(cfg.task_name_prefix, past_records)
            next_n = max_n + 1

        for ev in events_sorted:
            # Check if this event already exists in Notion
            # We verify existence later in differ, but here we enforce the correct sequence name
            ev.task_name = f"{ev.task_name_prefix} ({next_n})"

            if cfg.numbering_resets and cfg.period_size:
                next_n = next_n + 1 if next_n < cfg.period_size else 1
            else:
                next_n += 1

            # Update description with period info if applicable
            if cfg.period_size and cfg.numbering_resets and cfg.description_template:
                    # Calculate which period we're in
                    # Note: This is an approximation. Ideally we count total records.
                    # Use len(past_records) assuming they are all valid classes of this type
                    current_total = len(past_records)
                    total_count = current_total + (
                        events_sorted.index(ev)
                        - sum(
                            1
                            for e in events_sorted[: events_sorted.index(ev)]
                            if _find_matching_record(
                                e.task_name_prefix, e.start_time, all_records
                            )
                        )
                    )
                    period = (total_count // cfg.period_size) + 1
                    ev.description = cfg.description_template.replace(
                        "{period}", str(period)
                    )
