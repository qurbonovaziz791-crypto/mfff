from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from ninja import Router, Schema

from api.auth import MobileOrSessionAuth
from blogs import storage as blog_storage

User = get_user_model()

router = Router(tags=["mobile", "insights"])
auth = MobileOrSessionAuth()


class MoodBarOut(Schema):
    slug: str
    label: str
    count: int
    pct: int


class StatsBlockOut(Schema):
    label: str
    range: str
    total: int
    bars: list[MoodBarOut]


class StatsOut(Schema):
    streak_days: int
    blocks: list[StatsBlockOut]


def _bars(by_mood: dict[str, int], total: int) -> list[MoodBarOut]:
    if not total or not by_mood:
    # noqa: E701
        return []
    out: list[MoodBarOut] = []
    for slug, c in sorted(by_mood.items(), key=lambda x: -x[1]):
        out.append(
            MoodBarOut(
                slug=str(slug),
                label=str(blog_storage.mood_label(slug)),
                count=int(c),
                pct=int(round(100 * int(c) / int(total))),
            )
        )
    return out


@router.get("/stats", auth=auth, response=StatsOut)
def stats(request):
    me: User = request.auth
    today = date.today()

    start_week = (today - timedelta(days=6)).isoformat()
    end_week = today.isoformat()

    # previous month range
    if today.month == 1:
        py, pm = today.year - 1, 12
    else:
        py, pm = today.year, today.month - 1
    start_prev_month = date(py, pm, 1).isoformat()
    # last day of prev month
    next_month = date(py, pm, 28) + timedelta(days=10)
    last_prev_month = date(next_month.year, next_month.month, 1) - timedelta(days=1)
    end_prev_month = last_prev_month.isoformat()

    start_ytd = date(today.year, 1, 1).isoformat()
    end_ytd = today.isoformat()

    streak_days = blog_storage.user_writing_streak_days(user_id=me.id, username=me.username)

    tw, mw_week = blog_storage.user_mood_stats_in_range(
        user_id=me.id, username=me.username, date_from=start_week, date_to=end_week
    )
    tm, mw_month = blog_storage.user_mood_stats_in_range(
        user_id=me.id, username=me.username, date_from=start_prev_month, date_to=end_prev_month
    )
    tytd, mw_ytd = blog_storage.user_mood_stats_in_range(
        user_id=me.id, username=me.username, date_from=start_ytd, date_to=end_ytd
    )

    blocks = [
        StatsBlockOut(label="O‘tgan 7 kun", range=f"{start_week} — {end_week}", total=int(tw), bars=_bars(mw_week, int(tw))),
        StatsBlockOut(label="O‘tgan oy", range=f"{start_prev_month} — {end_prev_month}", total=int(tm), bars=_bars(mw_month, int(tm))),
        StatsBlockOut(label="Joriy yil", range=f"{start_ytd} — {end_ytd}", total=int(tytd), bars=_bars(mw_ytd, int(tytd))),
    ]
    return StatsOut(streak_days=int(streak_days), blocks=blocks)


class ArchiveDayOut(Schema):
    day: int
    count: int


class ArchiveOut(Schema):
    year: int
    month: int
    days: list[ArchiveDayOut]


@router.get("/archive", auth=auth, response=ArchiveOut)
def archive(request, year: Optional[int] = None, month: Optional[int] = None):
    me: User = request.auth
    now = datetime.now()
    y = int(year or now.year)
    m = int(month or now.month)
    m = max(1, min(12, m))
    counts = blog_storage.calendar_day_counts(user_id=me.id, username=me.username, year=y, month=m)
    days = [ArchiveDayOut(day=int(d), count=int(counts.get(d, 0))) for d in range(1, 32) if d <= 31]
    return ArchiveOut(year=y, month=m, days=days)

