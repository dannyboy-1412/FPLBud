from datetime import UTC, datetime

from fplcore.gameweeks import pick_started_gameweek, pick_upcoming_gameweek

NOW = datetime(2026, 10, 21, 11, 0, tzinfo=UTC)


def _gw(gw_id: int, deadline: datetime, *, is_next: bool = False, is_current: bool = False) -> dict:
    return {
        "id": gw_id,
        "deadline_time": deadline,
        "is_next": is_next,
        "is_current": is_current,
    }


def test_stale_next_flag_rolls_forward_after_the_deadline() -> None:
    gameweeks = [
        _gw(6, datetime(2026, 10, 10, 10, 0, tzinfo=UTC), is_current=True),
        _gw(7, datetime(2026, 10, 17, 10, 0, tzinfo=UTC), is_next=True),
        _gw(8, datetime(2026, 10, 23, 17, 30, tzinfo=UTC)),
    ]
    assert pick_upcoming_gameweek(gameweeks, NOW)["id"] == 8
    assert pick_started_gameweek(gameweeks, NOW)["id"] == 7


def test_fresh_next_flag_is_kept_while_its_deadline_is_ahead() -> None:
    gameweeks = [
        _gw(7, datetime(2026, 10, 17, 10, 0, tzinfo=UTC), is_current=True),
        _gw(8, datetime(2026, 10, 23, 17, 30, tzinfo=UTC), is_next=True),
    ]
    assert pick_upcoming_gameweek(gameweeks, NOW)["id"] == 8


def test_season_over_uses_the_last_gameweek() -> None:
    gameweeks = [
        _gw(37, datetime(2027, 5, 16, 14, 0, tzinfo=UTC)),
        _gw(38, datetime(2027, 5, 23, 15, 0, tzinfo=UTC), is_next=True),
    ]
    later = datetime(2027, 5, 24, 12, 0, tzinfo=UTC)
    assert pick_upcoming_gameweek(gameweeks, later)["id"] == 38
    assert pick_started_gameweek(gameweeks, later)["id"] == 38


def test_no_gameweeks() -> None:
    assert pick_upcoming_gameweek([], NOW) is None
    assert pick_started_gameweek([], NOW) is None
