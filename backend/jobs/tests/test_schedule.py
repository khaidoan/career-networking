"""Job fetching requirements, the daily fetch time, and whether a run is due."""

from datetime import UTC, datetime, timedelta

import pytest

from src.models import Preferences
from src.schedule import (
    is_due,
    is_valid_timezone,
    last_scheduled_time,
    missing_for_fetching,
    next_scheduled_time,
)

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("fetch_time", "timezone", "last", "next_"),
    [
        # Today's time has passed.
        (
            "06:00",
            "UTC",
            datetime(2026, 10, 6, 6, 0, tzinfo=UTC),
            datetime(2026, 10, 7, 6, 0, tzinfo=UTC),
        ),
        # Today's time is still ahead.
        (
            "18:30",
            "UTC",
            datetime(2026, 10, 5, 18, 30, tzinfo=UTC),
            datetime(2026, 10, 6, 18, 30, tzinfo=UTC),
        ),
        # 07:00 in Los Angeles (PDT, UTC-7) is 14:00 UTC.
        (
            "07:00",
            "America/Los_Angeles",
            datetime(2026, 10, 6, 14, 0, tzinfo=UTC),
            datetime(2026, 10, 7, 14, 0, tzinfo=UTC),
        ),
        # A legacy alias some browsers report.
        (
            "20:00",
            "Asia/Calcutta",
            datetime(2026, 10, 6, 14, 30, tzinfo=UTC),
            datetime(2026, 10, 7, 14, 30, tzinfo=UTC),
        ),
    ],
)
def test_last_and_next_scheduled_time(
    fetch_time: str, timezone: str, last: datetime, next_: datetime
) -> None:
    assert last_scheduled_time(NOW, fetch_time, timezone) == last
    assert next_scheduled_time(NOW, fetch_time, timezone) == next_


def test_scheduled_times_follow_daylight_saving_changes() -> None:
    # Los Angeles leaves daylight saving on 1 November: 07:00 local moves from 14:00 to 15:00 UTC.
    before = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    assert next_scheduled_time(before, "07:00", "America/Los_Angeles") == datetime(
        2026, 11, 1, 15, 0, tzinfo=UTC
    )


def test_a_run_is_due_until_one_starts_at_or_shortly_before_the_scheduled_time() -> None:
    scheduled = datetime(2026, 10, 6, 6, 0, tzinfo=UTC)

    assert is_due(NOW, "06:00", "UTC", None)
    assert is_due(NOW, "06:00", "UTC", scheduled - timedelta(days=1))
    # A restart-triggered run 30 minutes early counts as the day's run.
    assert not is_due(NOW, "06:00", "UTC", scheduled - timedelta(minutes=30))
    assert not is_due(NOW, "06:00", "UTC", scheduled + timedelta(minutes=5))
    # Moving the time later today makes it due again once that time comes.
    assert not is_due(NOW, "16:00", "UTC", scheduled)
    assert is_due(NOW + timedelta(hours=1, minutes=5), "16:00", "UTC", scheduled)


@pytest.mark.parametrize(
    ("fetch_time", "timezone"),
    [(None, "UTC"), ("06:00", None), ("25:00", "UTC"), ("06:00", "Not/AZone")],
)
def test_an_unset_or_invalid_schedule_is_never_due(
    fetch_time: str | None, timezone: str | None
) -> None:
    assert not is_due(NOW, fetch_time, timezone, None)


def test_missing_for_fetching_lists_every_unset_requirement() -> None:
    assert missing_for_fetching(None) == [
        "desired_titles",
        "country",
        "fetch_time",
        "fetch_timezone",
    ]
    partial = Preferences(id=1, desired_titles=[" "], country="US", fetch_time="06:00")
    assert missing_for_fetching(partial) == ["desired_titles", "fetch_timezone"]
    complete = Preferences(
        id=1,
        desired_titles=["Backend Engineer"],
        country="US",
        fetch_time="06:00",
        fetch_timezone="Europe/Berlin",
    )
    assert missing_for_fetching(complete) == []


@pytest.mark.parametrize(
    ("name", "valid"),
    [("Europe/Berlin", True), ("UTC", True), ("America", False), ("../etc/passwd", False)],
)
def test_is_valid_timezone(name: str, valid: bool) -> None:
    assert is_valid_timezone(name) is valid
