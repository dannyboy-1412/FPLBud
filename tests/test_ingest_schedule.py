from datetime import UTC, datetime, timedelta

from ingest.schedule import deadline_is_soon, is_lock_morning

LOCK_CHECK = datetime(2027, 1, 5, 9, 15, tzinfo=UTC)  # Tuesday, after a Monday night kickoff


def test_lock_morning_is_the_uk_day_after_the_final_kickoff() -> None:
    monday_night = datetime(2027, 1, 4, 20, 0, tzinfo=UTC)
    assert is_lock_morning([monday_night], LOCK_CHECK)
    assert not is_lock_morning([monday_night], LOCK_CHECK + timedelta(days=1))


def test_lock_morning_uses_the_uk_date_during_british_summer_time() -> None:
    # 20:00 BST Monday is 19:00 UTC. Tuesday 09:15 UTC is still Tuesday in the UK.
    monday_night = datetime(2026, 8, 17, 19, 0, tzinfo=UTC)
    tuesday_morning = datetime(2026, 8, 18, 9, 15, tzinfo=UTC)
    assert is_lock_morning([monday_night], tuesday_morning)
    assert not is_lock_morning([monday_night], monday_night)


def test_lock_morning_is_false_when_no_gameweek_has_a_kickoff() -> None:
    assert not is_lock_morning([], LOCK_CHECK)


def test_deadline_inside_48_hours_is_soon() -> None:
    now = datetime(2027, 1, 8, 8, 0, tzinfo=UTC)  # Friday
    saturday = datetime(2027, 1, 9, 11, 0, tzinfo=UTC)
    assert deadline_is_soon(saturday, now)


def test_deadline_further_than_48_hours_is_not_soon() -> None:
    now = datetime(2027, 1, 8, 8, 0, tzinfo=UTC)
    next_week = now + timedelta(hours=48, seconds=1)
    assert not deadline_is_soon(next_week, now)


def test_deadline_already_passed_is_not_soon() -> None:
    now = datetime(2027, 1, 9, 12, 0, tzinfo=UTC)
    earlier = datetime(2027, 1, 9, 11, 0, tzinfo=UTC)
    assert not deadline_is_soon(earlier, now)
    assert not deadline_is_soon(None, now)
