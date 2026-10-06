"""Whether job fetching is enabled, the daily fetch time, and whether a run is due.

Fetching is enabled only once the Profile page has desired titles, a country, a daily fetch time
and its time zone saved. The scheduler (``backend/jobs/crontab``) calls
``python -m src.fetcher --if-due`` every few minutes; a run is due when none has started since
the most recent scheduled time (or in the hour before it). Every run records its start, including
the one each container start triggers, so a restart close to the scheduled time does not run
twice.
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.models import Preferences

FetchingRequirement = Literal["desired_titles", "country", "fetch_time", "fetch_timezone"]

FETCH_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
# A run that started this long before the scheduled time counts as that day's run, so a restart
# shortly before it is not followed by a second full run.
EARLY_RUN_GRACE = timedelta(hours=1)


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    # A folder such as "America" raises OSError; a malformed name, ValueError.
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def is_valid_schedule(fetch_time: str | None, timezone: str | None) -> bool:
    return bool(
        fetch_time
        and FETCH_TIME_PATTERN.match(fetch_time)
        and timezone
        and is_valid_timezone(timezone)
    )


def missing_for_fetching(preferences: Preferences | None) -> list[FetchingRequirement]:
    """The saved values job fetching still needs; empty when fetching is enabled."""
    if preferences is None:
        return ["desired_titles", "country", "fetch_time", "fetch_timezone"]
    missing: list[FetchingRequirement] = []
    if not any(title.strip() for title in preferences.desired_titles or []):
        missing.append("desired_titles")
    if not preferences.country:
        missing.append("country")
    if not FETCH_TIME_PATTERN.match(preferences.fetch_time or ""):
        missing.append("fetch_time")
    if not (preferences.fetch_timezone and is_valid_timezone(preferences.fetch_timezone)):
        missing.append("fetch_timezone")
    return missing


def _scheduled_on(day: date, fetch_time: str, timezone: str) -> datetime:
    match = FETCH_TIME_PATTERN.match(fetch_time)
    if match is None:
        raise ValueError(f"invalid fetch time {fetch_time!r}")
    # Wall-clock time in the zone; a time skipped by a DST change maps to just after it.
    local = datetime.combine(day, time(int(match[1]), int(match[2])), tzinfo=ZoneInfo(timezone))
    return local.astimezone(UTC)


def last_scheduled_time(now: datetime, fetch_time: str, timezone: str) -> datetime:
    """The latest daily ``fetch_time`` in ``timezone`` that is not after ``now``, in UTC."""
    today = now.astimezone(ZoneInfo(timezone)).date()
    scheduled = _scheduled_on(today, fetch_time, timezone)
    if scheduled <= now:
        return scheduled
    return _scheduled_on(today - timedelta(days=1), fetch_time, timezone)


def next_scheduled_time(now: datetime, fetch_time: str, timezone: str) -> datetime:
    """The first daily ``fetch_time`` in ``timezone`` after ``now``, in UTC."""
    today = now.astimezone(ZoneInfo(timezone)).date()
    scheduled = _scheduled_on(today, fetch_time, timezone)
    if scheduled > now:
        return scheduled
    return _scheduled_on(today + timedelta(days=1), fetch_time, timezone)


def is_due(
    now: datetime,
    fetch_time: str | None,
    timezone: str | None,
    last_started: datetime | None,
) -> bool:
    """True when the schedule is set and no run has started since (or just before) its most
    recent time. An unset or invalid schedule is never due: fetching is disabled."""
    if fetch_time is None or timezone is None or not is_valid_schedule(fetch_time, timezone):
        return False
    if last_started is None:
        return True
    return last_started < last_scheduled_time(now, fetch_time, timezone) - EARLY_RUN_GRACE
