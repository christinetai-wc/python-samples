"""Comparison logic: GCal/Fixed events vs Notion records."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config import GCAL_COURSES
from models import CourseEvent, DiffAction, DiffItem, DiffResult, NotionRecord

TPE = ZoneInfo("Asia/Taipei")


def compute_diff(
    gcal_events: list[CourseEvent],
    fixed_events: list[CourseEvent],
    notion_records: list[NotionRecord],
    start: datetime,
    end: datetime,
) -> DiffResult:
    """Compare all sources against Notion and produce diff."""
    result = DiffResult()
    _diff_gcal(gcal_events, notion_records, result, start, end)
    _diff_fixed(fixed_events, notion_records, result)

    # Sort each list chronologically
    for lst in [
        result.skipped,
        result.to_add,
        result.time_changed,
        result.title_changed,
        result.gcal_cancelled,
        result.fixed_missing,
    ]:
        lst.sort(key=lambda d: d.sort_key)

    return result


def _diff_gcal(
    events: list[CourseEvent],
    records: list[NotionRecord],
    result: DiffResult,
    start: datetime,
    end: datetime,
) -> None:
    """Compare GCal events against Notion records."""
    matched_notion_ids: set[str] = set()

    for ev in events:
        ev_date = ev.start_time.date()
        match = _find_notion_match(ev.task_name_prefix, ev_date, records)

        if match:
            matched_notion_ids.add(match.page_id)
            
            time_diff = not _same_start_time(ev.start_time, match.start_time)
            title_diff = ev.task_name != match.task_name

            if time_diff:
                result.time_changed.append(
                    DiffItem(
                        action=DiffAction.UPDATE_TIME,
                        event=ev,
                        notion_record=match,
                        detail=(
                            f"Notion: {_fmt_time(match.start_time)} "
                            f"→ GCal: {_fmt_time(ev.start_time)}"
                        ),
                    )
                )
            
            if title_diff:
                result.title_changed.append(
                    DiffItem(
                        action=DiffAction.UPDATE_TITLE,
                        event=ev,
                        notion_record=match,
                        detail=f"Notion: {match.task_name} → {ev.task_name}",
                    )
                )

            if not time_diff and not title_diff:
                result.skipped.append(
                    DiffItem(action=DiffAction.SKIP, event=ev, notion_record=match)
                )
        else:
            result.to_add.append(
                DiffItem(action=DiffAction.ADD, event=ev, notion_record=None)
            )

    # Check for GCal cancellations: Notion has future Done=❌ but GCal doesn't
    gcal_prefixes = {ev.task_name_prefix for ev in events}
    gcal_dates_by_prefix: dict[str, set] = {}
    for ev in events:
        gcal_dates_by_prefix.setdefault(ev.task_name_prefix, set()).add(
            ev.start_time.date()
        )

    for rec in records:
        if rec.page_id in matched_notion_ids:
            continue
        if rec.done:
            continue
        if not rec.start_time or rec.start_time < start:
            continue
        for prefix in gcal_prefixes:
            if prefix in rec.task_name:
                # This Notion record matches a GCal course but wasn't matched to any event
                result.gcal_cancelled.append(
                    DiffItem(
                        action=DiffAction.GCAL_CANCELLED,
                        event=None,
                        notion_record=rec,
                        detail="Notion 有，GCal 無",
                    )
                )
                break


def _diff_fixed(
    events: list[CourseEvent],
    records: list[NotionRecord],
    result: DiffResult,
) -> None:
    """Compare fixed-schedule expected dates against Notion records."""
    for ev in events:
        ev_date = ev.start_time.date()
        match = _find_notion_match(ev.task_name_prefix, ev_date, records)
        if match:
            if ev.task_name != match.task_name:
                result.title_changed.append(
                    DiffItem(
                        action=DiffAction.UPDATE_TITLE,
                        event=ev,
                        notion_record=match,
                        detail=f"Notion: {match.task_name} → {ev.task_name}",
                    )
                )
            else:
                result.skipped.append(
                    DiffItem(action=DiffAction.SKIP, event=ev, notion_record=match)
                )
        else:
            result.fixed_missing.append(
                DiffItem(action=DiffAction.FIXED_MISSING, event=ev, notion_record=None)
            )


def _find_notion_match(
    prefix: str, date, records: list[NotionRecord]
) -> NotionRecord | None:
    """Find a Notion record matching the prefix and same date (TPE)."""
    for rec in records:
        if rec.start_time and rec.start_time.date() == date:
            if prefix in rec.task_name:
                return rec
    return None


def _same_start_time(a: datetime | None, b: datetime | None) -> bool:
    """Compare two datetimes, treating both as TPE."""
    if a is None or b is None:
        return a is None and b is None
    # Compare with minute precision (ignore seconds)
    return a.replace(second=0, microsecond=0) == b.replace(second=0, microsecond=0)


def _fmt_time(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "?"
    return dt.strftime("%m/%d %H:%M")
