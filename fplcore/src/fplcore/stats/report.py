from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fplcore.constants import SQUAD_SCORE_HIGH_PERCENTILE, SQUAD_SCORE_LOW_PERCENTILE
from fplcore.metrics.combine import availability, combined_score, playing_share, projected_points
from fplcore.stats.insights import finishing_variance, in_form

XI_SIZE = 11
REPORT_TOP_N = 5
MIN_RETURN_GAP = 0.5
SCORE_KEYS = ("form", "fixture", "home", "xgi", "value", "minutes", "trend")
_STRONG_MARK = 8.0
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
    """Rate this week's starting 11 out of 10.

    Each starter is marked once, from an ordinary player with a game up to a
    premium one. The squad score is the average of those 11 marks. An empty
    place counts as 0.
    """
    playing = [float(value) for value in field if float(value) > 0]
    if len(playing) < 2:
        return 0.0
    low = _percentile(playing, SQUAD_SCORE_LOW_PERCENTILE)
    high = _percentile(playing, SQUAD_SCORE_HIGH_PERCENTILE)
    slots = [float(value) for value in projections[:XI_SIZE]]
    slots.extend(0.0 for _ in range(XI_SIZE - len(slots)))
    if high <= low:
        return 5.0 if any(value > 0 for value in slots) else 0.0
    marks = [_player_mark(value, low, high) for value in slots]
    return round(sum(marks) / XI_SIZE, 1)


def _player_mark(projection: float, low: float, high: float) -> float:
    raw = (projection - low) / (high - low) * 10.0
    return min(10.0, max(0.0, raw))


@dataclass(frozen=True)
class StarterOutlook:
    """Facts about one starter that the squad-score reason is allowed to cite."""

    name: str
    projection: float
    blank: bool = False
    unlikely: bool = False
    not_starting: bool = False


@dataclass(frozen=True)
class SquadScoreNotes:
    """The two lists under the score: the strong picks, and why it is not a 10."""

    added: tuple[str, ...] = ()
    short_of_10: tuple[str, ...] = ()

    def payload(self) -> dict[str, list[str]]:
        return {"added": list(self.added), "short_of_10": list(self.short_of_10)}


@dataclass(frozen=True)
class SquadScore:
    """A squad score out of 10, the facts behind it, and a sentence if no model is called."""

    value: float
    reason: str
    starters: tuple[StarterOutlook, ...] = ()
    notes: SquadScoreNotes = SquadScoreNotes()


def explain_squad_score(starters: list[StarterOutlook], field: list[float]) -> SquadScore:
    """Score a starting 11 out of 10 and name who makes it strong and who keeps it off 10."""
    starters = starters[:XI_SIZE]
    value = squad_score_for_xi([starter.projection for starter in starters], field)
    notes = _score_notes(starters, field, value)
    return SquadScore(
        value=value,
        reason=_squad_score_reason(field, value, notes),
        starters=tuple(starters),
        notes=notes,
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


def _squad_score_reason(field: list[float], score: float, notes: SquadScoreNotes) -> str:
    playing = _playing_field(field)
    if len(playing) < 2:
        return "Not enough players have a game this week to score this side."
    low = _percentile(playing, SQUAD_SCORE_LOW_PERCENTILE)
    high = _percentile(playing, SQUAD_SCORE_HIGH_PERCENTILE)
    if high <= low:
        if score > 0:
            return "Players with a game all look the same this week, so this side sits in the middle."
        return "The starting 11 has nothing this week."
    lines = [*notes.added, *notes.short_of_10]
    if not lines:
        return "How strong your starting 11 looks this week."
    return " ".join(lines)


def _score_notes(
    starters: list[StarterOutlook],
    field: list[float],
    score: float,
) -> SquadScoreNotes:
    playing = _playing_field(field)
    if len(playing) < 2:
        return SquadScoreNotes()
    low = _percentile(playing, SQUAD_SCORE_LOW_PERCENTILE)
    high = _percentile(playing, SQUAD_SCORE_HIGH_PERCENTILE)
    if high <= low:
        return SquadScoreNotes()
    marks = [_player_mark(starter.projection, low, high) for starter in starters]
    paired = list(zip(starters, marks, strict=True))
    added = _strong_lines(paired) if score > 0 else ()
    short = _short_lines(starters, paired) if score < 10 else ()
    return SquadScoreNotes(added=tuple(added), short_of_10=tuple(short))


def _strong_lines(paired: list[tuple[StarterOutlook, float]]) -> tuple[str, ...]:
    strong = _ordered(paired, highest_first=True, include=lambda mark: mark >= _STRONG_MARK)
    if len(strong) == XI_SIZE:
        return ("All 11 starters are strong picks this week.",)
    line = _pick_line(strong, "is a strong pick this week", "are strong picks this week")
    return (line,) if line else ()


def _short_lines(
    starters: list[StarterOutlook],
    paired: list[tuple[StarterOutlook, float]],
) -> tuple[str, ...]:
    lines: list[str] = []
    if len(starters) < XI_SIZE:
        lines.append(_places_line(len(starters)))
    blanks = [starter for starter in starters if starter.blank]
    doubts = [starter for starter in starters if starter.unlikely]
    benched = [starter for starter in starters if starter.not_starting]
    if blanks:
        lines.append(_pick_line(blanks, "has no game this week", "have no game this week"))
    if doubts:
        lines.append(_pick_line(doubts, "might not play", "might not play"))
    if benched:
        lines.append(_pick_line(benched, "has not been starting", "have not been starting"))
    weakest = _ordered(
        paired,
        highest_first=False,
        include=lambda mark: mark < _STRONG_MARK,
        only_playing=True,
    )
    holding = _pick_line(weakest, "is keeping this off a 10", "are the ones keeping this off a 10")
    if holding:
        lines.append(holding)
    return tuple(line for line in lines if line)


def _ordered(
    paired: list[tuple[StarterOutlook, float]],
    *,
    highest_first: bool,
    include: Callable[[float], bool],
    only_playing: bool = False,
) -> list[StarterOutlook]:
    chosen = [
        (index, starter, mark)
        for index, (starter, mark) in enumerate(paired)
        if include(mark) and (not only_playing or _is_playing(starter))
    ]
    chosen.sort(key=lambda item: (-item[2] if highest_first else item[2], item[0]))
    return [starter for _, starter, _ in chosen]


def _is_playing(starter: StarterOutlook) -> bool:
    return not starter.blank and not starter.unlikely and not starter.not_starting


def _places_line(count: int) -> str:
    if count == 0:
        return "None of the 11 places are filled."
    if count == 1:
        return "Only 1 of the 11 places is filled."
    return f"Only {count} of the 11 places are filled."


def _pick_line(starters: list[StarterOutlook], singular: str, plural: str) -> str:
    phrase, one_name = _listed([starter.name for starter in starters])
    if not phrase:
        if not starters:
            return ""
        if len(starters) == 1:
            return _finish(f"One starter {singular}")
        return _finish(f"{len(starters)} starters {plural}")
    verb = singular if one_name else plural
    return _finish(f"{phrase} {verb}")


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


def _finish(clause: str) -> str:
    sentence = _sentence(clause.strip())
    if not sentence or sentence.endswith("."):
        return sentence
    return f"{sentence}."


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
