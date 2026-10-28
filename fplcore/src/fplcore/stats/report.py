from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fplcore.constants import SQUAD_SCORE_HIGH_PERCENTILE, SQUAD_SCORE_LOW_PERCENTILE
from fplcore.metrics.combine import availability, combined_score, playing_share, projected_points
from fplcore.stats.insights import finishing_variance, in_form

XI_SIZE = 11
REPORT_TOP_N = 5
MIN_RETURN_GAP = 0.5
SCORE_KEYS = ("form", "fixture", "home", "xgi", "value", "minutes", "trend")
_MEDIAN_PERCENTILE = 50.0
_STANDOUT_PERCENTILE = 90.0
_CLEAR_MAJORITY = 8
_UNLIKELY_AVAILABILITY = 0.5


def xi_element_ids(squad_players: list[dict[str, Any]]) -> list[int]:
    starters: list[tuple[int, int]] = []
    for player in squad_players:
        pos = int(player.get("squad_position") or player.get("position") or 0)
        if pos < 1 or pos > XI_SIZE:
            continue
        element = int(player.get("element") or player.get("id") or 0)
        if element:
            starters.append((pos, element))
    starters.sort(key=lambda item: item[0])
    return [element for _, element in starters[:XI_SIZE]]


def scores_from_metric_row(row: dict[str, Any]) -> dict[str, float]:
    return {key: float(row.get(f"{key}_score") or 0) for key in SCORE_KEYS}


def projection_for_row(row: dict[str, Any], weights: dict[str, float] | None) -> float:
    season_minutes = int(row["minutes"]) if "minutes" in row and row["minutes"] is not None else None
    return projected_points(
        score=combined_score(scores_from_metric_row(row), weights),
        fixture_count=int(row.get("fixture_count") or 0),
        avail=availability(
            chance_of_playing_next_round=row.get("chance_of_playing_next_round"),
            status=str(row.get("status") or "a"),
            k=1,
        ),
        minutes=playing_share(float(row.get("minutes_score") or 0), season_minutes),
    )


def xi_projections(
    xi_ids: list[int],
    rows_by_id: dict[int, dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> list[float]:
    projections: list[float] = []
    for pid in xi_ids[:XI_SIZE]:
        row = rows_by_id.get(pid)
        projections.append(projection_for_row(row, weights) if row else 0.0)
    return projections


def _xi_points_with_captain(projections: list[float]) -> float:
    slots = [float(value) for value in projections[:XI_SIZE]]
    slots.extend(0.0 for _ in range(XI_SIZE - len(slots)))
    return sum(slots) + max(slots)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def squad_score_for_xi(projections: list[float], field: list[float]) -> float:
    """Rate this gameweek's estimated points out of 10.

    The estimate doubles the highest starter, the way a captain scores.
    Zero is an XI built from the 25th percentile of players with a fixture,
    and 10 is an XI built from the 98th. The marks move with the projections,
    so the same squad is not a 10 just because the week is a double.
    """
    estimated = _xi_points_with_captain(projections)
    playing = [float(value) for value in field if float(value) > 0]
    if len(playing) < 2:
        return 0.0
    slots = XI_SIZE + 1
    floor = slots * _percentile(playing, SQUAD_SCORE_LOW_PERCENTILE)
    ceiling = slots * _percentile(playing, SQUAD_SCORE_HIGH_PERCENTILE)
    if ceiling <= floor:
        return 5.0 if estimated > 0 else 0.0
    raw = (estimated - floor) / (ceiling - floor) * 10.0
    return round(min(10.0, max(0.0, raw)), 1)


@dataclass(frozen=True)
class StarterOutlook:
    """Facts about one starter that the squad-score reason is allowed to cite."""

    name: str
    projection: float
    blank: bool = False
    unlikely: bool = False
    not_starting: bool = False


@dataclass(frozen=True)
class SquadScore:
    """A squad score out of 10, the facts behind it, and a sentence if no model is called."""

    value: float
    reason: str
    starters: tuple[StarterOutlook, ...] = ()


def explain_squad_score(starters: list[StarterOutlook], field: list[float]) -> SquadScore:
    """Score an XI out of 10 and say what pushed it there."""
    value = squad_score_for_xi([starter.projection for starter in starters], field)
    return SquadScore(
        value=value,
        reason=_squad_score_reason(starters, field, value),
        starters=tuple(starters),
    )


def score_starting_xi(
    xi_ids: list[int],
    rows_by_id: dict[int, dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> SquadScore:
    """Score the next-gameweek XI from metric rows, with a reason."""
    ids = xi_ids[:XI_SIZE]
    projections = xi_projections(ids, rows_by_id, weights)
    field = [projection_for_row(row, weights) for row in rows_by_id.values()]
    outlooks = [
        _outlook(rows_by_id.get(player_id), projection)
        for player_id, projection in zip(ids, projections, strict=True)
    ]
    return explain_squad_score(outlooks, field)


def _outlook(row: dict[str, Any] | None, projection: float) -> StarterOutlook:
    if row is None:
        return StarterOutlook(name="", projection=projection, unlikely=True)
    fixture_count = int(row.get("fixture_count") or 0)
    season_minutes = int(row["minutes"]) if row.get("minutes") is not None else None
    share = playing_share(float(row.get("minutes_score") or 0), season_minutes)
    avail = availability(
        chance_of_playing_next_round=row.get("chance_of_playing_next_round"),
        status=str(row.get("status") or "a"),
        k=1,
    )
    blank = fixture_count <= 0
    not_starting = not blank and share <= 0
    unlikely = not blank and not not_starting and avail <= _UNLIKELY_AVAILABILITY
    return StarterOutlook(
        name=str(row.get("web_name") or ""),
        projection=projection,
        blank=blank,
        unlikely=unlikely,
        not_starting=not_starting,
    )


def _playing_field(field: list[float]) -> list[float]:
    return [float(value) for value in field if float(value) > 0]


def _squad_score_reason(starters: list[StarterOutlook], field: list[float], score: float) -> str:
    playing = _playing_field(field)
    if len(playing) < 2:
        return "Not enough players have a fixture to place this XI."
    low = _percentile(playing, SQUAD_SCORE_LOW_PERCENTILE)
    high = _percentile(playing, SQUAD_SCORE_HIGH_PERCENTILE)
    if high <= low:
        if score > 0:
            return "Players with a fixture all project the same, so the XI sits in the middle."
        return "The starting XI has nothing projected this week."
    detail = _score_detail(starters, playing, score)
    if not detail:
        return _score_band(score)
    return f"{_score_band(score)} {detail}"


def _score_band(score: float) -> str:
    if score >= 8:
        return "A premium XI this week."
    if score >= 6:
        return "Above the middle of the scale."
    if score >= 4:
        return "Around the middle of the scale."
    if score > 0:
        return "Closer to an ordinary XI than a premium one."
    return "At the bottom of the scale."


def _score_detail(starters: list[StarterOutlook], playing: list[float], score: float) -> str:
    if len(starters) < XI_SIZE:
        return _sentence(_short_xi_clause(len(starters)))

    blanks = [starter for starter in starters if starter.blank]
    doubts = [starter for starter in starters if starter.unlikely]
    benched = [starter for starter in starters if starter.not_starting]
    floor = _percentile(playing, SQUAD_SCORE_LOW_PERCENTILE)
    weak = [
        starter
        for starter in starters
        if not starter.blank
        and not starter.unlikely
        and not starter.not_starting
        and starter.projection < floor
    ]
    standout = _standout(starters, playing)
    drag = _drag_clause(blanks, doubts, benched, weak, len(starters))

    if standout is not None and score >= 8:
        lifted = _standout_sentence(standout, playing)
        if blanks or doubts or benched:
            return f"{lifted} {_sentence(drag)}"
        return lifted
    if drag and standout is not None and score >= 4:
        return _sentence(f"{_counted_twice(standout)}, but {drag}")
    if drag:
        return _sentence(drag)
    if standout is not None:
        return _standout_sentence(standout, playing)

    median = _percentile(playing, _MEDIAN_PERCENTILE)
    above = sum(1 for starter in starters if starter.projection >= median)
    if above >= _CLEAR_MAJORITY and score >= 6:
        if above == len(starters):
            return "Every starter projects above a typical player with a fixture."
        return f"{above} starters project above a typical player with a fixture."
    return "The starters project around the middle of players with a fixture."


def _drag_clause(
    blanks: list[StarterOutlook],
    doubts: list[StarterOutlook],
    benched: list[StarterOutlook],
    weak: list[StarterOutlook],
    squad_size: int,
) -> str:
    if blanks:
        return _named_clause(blanks, "no fixture this week", "has", "have")
    if doubts:
        return _named_clause(doubts, "unlikely to play", "is", "are")
    if benched:
        return _named_clause(benched, "not been starting", "has", "have")
    if weak:
        return _weak_clause(weak, squad_size)
    return ""


def _standout(starters: list[StarterOutlook], playing: list[float]) -> StarterOutlook | None:
    if not starters:
        return None
    best = max(starters, key=lambda starter: starter.projection)
    if best.projection <= 0:
        return None
    if best.projection < _percentile(playing, _STANDOUT_PERCENTILE):
        return None
    return best


def _counted_twice(starter: StarterOutlook) -> str:
    name = starter.name or "The best starter"
    return f"{name} is counted twice"


def _standout_sentence(starter: StarterOutlook, playing: list[float]) -> str:
    best = _percentile(playing, SQUAD_SCORE_HIGH_PERCENTILE)
    if starter.projection >= best:
        quality = "projects with the best of the field"
    else:
        quality = "is one of the best projections"
    return f"{_counted_twice(starter)} and {quality}."


def _named_clause(
    starters: list[StarterOutlook],
    description: str,
    singular: str,
    plural: str,
) -> str:
    phrase, one_name = _listed([starter.name for starter in starters])
    if not phrase:
        count = len(starters)
        subject = "one starter" if count == 1 else f"{count} starters"
        verb = singular if count == 1 else plural
        return f"{subject} {verb} {description}."
    verb = singular if one_name else plural
    return f"{phrase} {verb} {description}."


def _weak_clause(starters: list[StarterOutlook], squad_size: int) -> str:
    if squad_size and len(starters) >= squad_size:
        return "every starter projects below a typical player with a fixture."
    if len(starters) >= _CLEAR_MAJORITY:
        return "most of the XI projects below a typical starter."
    return _named_clause(starters, "below a typical starter", "projects", "project")


def _short_xi_clause(count: int) -> str:
    if count == 0:
        return "none of the 11 starters are set."
    if count == 1:
        return "only 1 of the 11 starters is set."
    return f"only {count} of the 11 starters are set."


def _listed(names: list[str]) -> tuple[str, bool]:
    cleaned = [name for name in names if name]
    if not cleaned:
        return "", True
    if len(cleaned) > 3:
        others = len(cleaned) - 2
        return f"{cleaned[0]}, {cleaned[1]} and {others} others", False
    if len(cleaned) == 1:
        return cleaned[0], True
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}", False
    return f"{cleaned[0]}, {cleaned[1]} and {cleaned[2]}", False


def _sentence(clause: str) -> str:
    if not clause:
        return clause
    return clause[0].upper() + clause[1:]


def xi_expected_points(
    xi_ids: list[int],
    rows_by_id: dict[int, dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    players: list[dict[str, Any]] = []
    total = 0.0
    for pid in xi_ids:
        row = rows_by_id.get(pid)
        if row is None:
            players.append({"id": pid, "web_name": str(pid), "proj": 0.0})
            continue
        proj = projection_for_row(row, weights)
        players.append({"id": pid, "web_name": row["web_name"], "proj": round(proj, 2)})
        total += proj
    players.sort(key=lambda p: float(p["proj"]), reverse=True)
    return {"total": round(total, 1), "players": players}


def performing_players(recent: list[dict[str, Any]], squad_ids: set[int]) -> list[dict[str, Any]]:
    scoped = [row for row in recent if int(row["id"]) in squad_ids]
    return in_form(scoped, n=REPORT_TOP_N)


def underperforming_players(players: list[dict[str, Any]], squad_ids: set[int]) -> list[dict[str, Any]]:
    scoped = [row for row in players if int(row["id"]) in squad_ids]
    rows = finishing_variance(scoped, n=REPORT_TOP_N)["underperformers"]
    return [row for row in rows if float(row["xgi_delta"]) >= MIN_RETURN_GAP]


def overperforming_players(players: list[dict[str, Any]], squad_ids: set[int]) -> list[dict[str, Any]]:
    scoped = [row for row in players if int(row["id"]) in squad_ids]
    rows = finishing_variance(scoped, n=REPORT_TOP_N)["overperformers"]
    return [row for row in rows if float(row["xgi_delta"]) <= -MIN_RETURN_GAP]
