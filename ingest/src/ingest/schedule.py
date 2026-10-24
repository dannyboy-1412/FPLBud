from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
PRE_DEADLINE_WINDOW = timedelta(hours=48)


def is_lock_morning(final_kickoffs: list[datetime], now: datetime) -> bool:
    """True on the UK morning after a gameweek's last kickoff.

    FPL confirms that gameweek's points at 09:00 UK the next day, so the
    history pull belongs on that morning and not after every match.
    """
    today = _aware(now).astimezone(UK).date()
    return any(_uk_date(kickoff) + timedelta(days=1) == today for kickoff in final_kickoffs)


def deadline_is_soon(
    deadline: datetime | None,
    now: datetime,
    window: timedelta = PRE_DEADLINE_WINDOW,
) -> bool:
    """True when the next deadline is still ahead and inside the window."""
    if deadline is None:
        return False
    remaining = _aware(deadline) - _aware(now)
    return timedelta(0) < remaining <= window


def _uk_date(moment: datetime) -> date:
    return _aware(moment).astimezone(UK).date()


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment
