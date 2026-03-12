"""Course definitions and constants for sync-notion."""

from __future__ import annotations

from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

TPE = ZoneInfo("Asia/Taipei")

NOTION_DATABASE_ID_DEFAULT = "202ecea7a5c7800abd51000b1008a72e"
INDEX_FILE_DEFAULT = "/Users/christine/self-study/sync_rule/sync-rules-index.md"

# Google Calendar API scope
GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


@dataclass
class GCalCourseConfig:
    """Configuration for a GCal-based course."""

    key: str
    calendar_id: str
    event_filter: str  # substring to match in event summary
    task_name_prefix: str
    has_numbering: bool
    numbering_resets: bool  # True = reset (1) each period; False = continuous
    category: str
    cost: int | None  # None = don't fill Notion Cost field
    description_template: str  # e.g. "第{period}期 $2600"
    period_size: int | None  # classes per period; None = no period
    default_hours: float


@dataclass
class FixedCourseConfig:
    """Configuration for a fixed-schedule course (no GCal)."""

    key: str
    task_name_prefix: str
    has_numbering: bool
    numbering_resets: bool
    category: str
    weekdays: list[int]  # 0=Mon, 1=Tue, ..., 6=Sun
    start_hour: int
    start_minute: int
    hours: float
    cost: int | None
    description_template: str
    period_size: int | None


# ── GCal-based courses ──────────────────────────────────

GCAL_COURSES: list[GCalCourseConfig] = [
    GCalCourseConfig(
        key="sophie_math",
        calendar_id="ea616397155ba456ca6d0a211121d367e502ce582108f335b164a516f8e0265c@group.calendar.google.com",
        event_filter="Neo",
        task_name_prefix="Sophie數學",
        has_numbering=True,
        numbering_resets=True,  # 每 10 堂一期，期末重置
        category="數學",
        cost=2600,
        description_template="第{period}期 共十堂 $26000",
        period_size=10,
        default_hours=2,
    ),
    GCalCourseConfig(
        key="nature",
        calendar_id="ef54b07d515698dbfe1edcbd35d304f2363bd770d5ccaf84d1e982671b47a9fc@group.calendar.google.com",
        event_filter="自學團",
        task_name_prefix="自然課",
        has_numbering=True,
        numbering_resets=True,  # 每 10 堂一期，期末重置
        category="自然",
        cost=1400,
        description_template="第{period}期 共十堂 $14000",
        period_size=10,
        default_hours=2,
    ),
    GCalCourseConfig(
        key="dance",
        calendar_id="9442cde168d527be787731243b8c0214e0e932425188165a5d77ac0ca1337903@group.calendar.google.com",
        event_filter="Lulu",
        task_name_prefix="舞蹈",
        has_numbering=True,
        numbering_resets=True,  # 每 10 堂一期，期末重置
        category="運動",
        cost=850,
        description_template="第{period}期 共十堂 $8500",
        period_size=10,
        default_hours=2,
    ),
    GCalCourseConfig(
        key="music",
        calendar_id="7e3cdcc1ed08d7ad2a9a935874a3214221413ed4423e196f1d0c7f1280efc3cd@group.calendar.google.com",
        event_filter="綾小路老師音樂",
        task_name_prefix="音樂創作",
        has_numbering=True,
        numbering_resets=True,  # 每 6 堂一期，期末重置
        category="音樂",
        cost=800,
        description_template="第{period}期 共六堂 $4800",
        period_size=6,
        default_hours=1.5,
    ),
    GCalCourseConfig(
        key="yoga",
        calendar_id="6d63b0c89c832a30a1b33c159fa65d046defdf49fb7f094f5d2acbf5a8b46316@group.calendar.google.com",
        event_filter="兒童瑜珈",
        task_name_prefix="兒童瑜珈",
        has_numbering=True,
        numbering_resets=True,  # 每 6 堂一期，期末重置
        category="運動",
        cost=450,
        description_template="共六堂 $2700",
        period_size=6,
        default_hours=1,
    ),
    GCalCourseConfig(
        key="coding",
        calendar_id="6d63b0c89c832a30a1b33c159fa65d046defdf49fb7f094f5d2acbf5a8b46316@group.calendar.google.com",
        event_filter="承軒程式課",
        task_name_prefix="程式設計課",
        has_numbering=True,
        numbering_resets=False,  # 連續編號
        category="科技",
        cost=None,
        description_template="",
        period_size=None,
        default_hours=2,
    ),
]


# ── Fixed-schedule courses ──────────────────────────────

FIXED_COURSES: list[FixedCourseConfig] = [
    FixedCourseConfig(
        key="emo",
        task_name_prefix="EMO",
        has_numbering=False,
        numbering_resets=False,
        category="英文",
        weekdays=[1, 3],  # Tue, Thu
        start_hour=20,
        start_minute=0,
        hours=1,
        cost=320,
        description_template="",
        period_size=None,
    ),
    FixedCourseConfig(
        key="lifang",
        task_name_prefix="麗芳自學課",
        has_numbering=False,
        numbering_resets=False,
        category="社會",
        weekdays=[2, 4],  # Wed, Fri
        start_hour=9,
        start_minute=0,
        hours=3,
        cost=3000,
        description_template="",
        period_size=None,
    ),
    FixedCourseConfig(
        key="basketball",
        task_name_prefix="籃球",
        has_numbering=True,
        numbering_resets=True,
        category="運動",
        weekdays=[4],  # Fri
        start_hour=19,
        start_minute=40,
        hours=1.5,
        cost=500,
        description_template="共十堂",
        period_size=10,
    ),
    FixedCourseConfig(
        key="charie",
        task_name_prefix="Charie英文",
        has_numbering=True,
        numbering_resets=True,
        category="英文",
        weekdays=[5],  # Sat
        start_hour=15,
        start_minute=0,
        hours=2,
        cost=1540,
        description_template="共24堂 $36960",
        period_size=24,
    ),
    FixedCourseConfig(
        key="hong_math",
        task_name_prefix="Hong數學",
        has_numbering=False,
        numbering_resets=False,
        category="數學",
        weekdays=[0],  # Mon
        start_hour=9,
        start_minute=30,
        hours=2,
        cost=1800,
        description_template="",
        period_size=None,
    ),
    FixedCourseConfig(
        key="finance",
        task_name_prefix="看懂財報",
        has_numbering=True,
        numbering_resets=False,
        category="財商",
        weekdays=[0,1,2,3,5,6],
        start_hour=12,
        start_minute=0,
        hours=1,
        cost=0,
        description_template="",
        period_size=100,
    ),
]
