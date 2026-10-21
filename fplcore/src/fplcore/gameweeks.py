from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any


def pick_upcoming_gameweek(
    gameweeks: Sequence[Mapping[str, Any]],
    now: datetime,
) -> Mapping[str, Any] | None:
    """Gameweek still open for planning.

    ``is_next`` is correct after a fresh ingest. A stale copy keeps the previous
    gameweek flagged once its deadline has passed, so roll forward to the next
    deadline that is still ahead.
    """
    if not gameweeks:
        return None
    moment = _as_utc(now)
    flagged = next((gameweek for gameweek in gameweeks if gameweek.get("is_next")), None)
    flagged_deadline = _deadline(flagged) if flagged is not None else None
    if flagged is not None and flagged_deadline is not None and flagged_deadline > moment:
        return flagged
    upcoming = [gameweek for gameweek in gameweeks if _is_after(gameweek, moment)]
    if upcoming:
        return min(upcoming, key=lambda gameweek: (_deadline(gameweek), int(gameweek["id"])))
    return max(gameweeks, key=lambda gameweek: int(gameweek["id"]))


def pick_started_gameweek(
    gameweeks: Sequence[Mapping[str, Any]],
    now: datetime,
) -> Mapping[str, Any] | None:
    """Latest gameweek whose deadline has passed."""
    moment = _as_utc(now)
    started = [gameweek for gameweek in gameweeks if _is_due(gameweek, moment)]
    if started:
        return max(started, key=lambda gameweek: (_deadline(gameweek), int(gameweek["id"])))
    return next((gameweek for gameweek in gameweeks if gameweek.get("is_current")), None)


def _is_after(gameweek: Mapping[str, Any], moment: datetime) -> bool:
    deadline = _deadline(gameweek)
    return deadline is not None and deadline > moment


def _is_due(gameweek: Mapping[str, Any], moment: datetime) -> bool:
    deadline = _deadline(gameweek)
    return deadline is not None and deadline <= moment


def _deadline(gameweek: Mapping[str, Any] | None) -> datetime | None:
    if gameweek is None:
        return None
    value = gameweek.get("deadline_time")
    if not isinstance(value, datetime):
        return None
    return _as_utc(value)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
