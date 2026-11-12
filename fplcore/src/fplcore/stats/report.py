from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fplcore.constants import SQUAD_SCORE_HIGH_PERCENTILE, SQUAD_SCORE_LOW_PERCENTILE
from fplcore.metrics.combine import availability, combined_score, playing_share, projected_points
from fplcore.stats.insights import in_form

XI_SIZE = 11
REPORT_TOP_N = 5
SCORE_KEYS = ("form", "fixture", "home", "xgi", "value", "minutes", "trend")
_STRONG_MARK = 8.0
_UNLIKELY_AVAILABILITY = 0.5
_EASY_FIXTURE = 0.70
_HARD_FIXTURE = 0.35
_STRONG_FORM = 0.75
_POOR_FORM = 0.30
_STRONG_XGI = 0.75
_WEAK_XGI = 0.30
_SHAKY_MINUTES = 0.40


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
    form: float | None = None
    fixture: float | None = None
    xgi: float | None = None
    minutes_security: float | None = None


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
    """Score a starting 11 out of 10 and say who is strong, who holds it back, and why."""
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
        form=_optional_score(row, "form_score"),
        fixture=_optional_score(row, "fixture_score"),
        xgi=_optional_score(row, "xgi_score"),
        minutes_security=_optional_score(row, "minutes_score"),
    )


def _optional_score(row: dict[str, Any], key: str) -> float | None:
    raw = row.get(key)
    if raw is None:
        return None
    return float(raw)


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
    bar = low + (_STRONG_MARK / 10.0) * (high - low)
    added = _strong_lines(paired, bar) if score > 0 else ()
    short = _short_lines(starters, paired, bar) if score < 10 else ()
    return SquadScoreNotes(added=tuple(added), short_of_10=tuple(short))


def _strong_lines(paired: list[tuple[StarterOutlook, float]], bar: float) -> tuple[str, ...]:
    strong = _ordered(paired, highest_first=True, include=lambda mark: mark >= _STRONG_MARK)
    if not strong:
        return ()
    if len(strong) == 1:
        return (_finish(_standout(strong[0], bar)),)
    if _same_projected_points(strong):
        return (_finish(_tied_strong(strong, bar)),)
    lines = [_finish(_lead_strong(strong[0], bar, len(strong))), _finish(_standout(strong[1], bar))]
    rest = strong[2:]
    if rest:
        lines.append(_finish(_rest_strong(rest)))
    return tuple(lines)


def _short_lines(
    starters: list[StarterOutlook],
    paired: list[tuple[StarterOutlook, float]],
    bar: float,
) -> tuple[str, ...]:
    lines: list[str] = []
    if len(starters) < XI_SIZE:
        lines.append(_places_line(len(starters)))
    blanks = [starter for starter in starters if starter.blank]
    doubts = [starter for starter in starters if starter.unlikely]
    benched = [starter for starter in starters if starter.not_starting]
    if blanks:
        lines.append(
            _pick_line(
                blanks,
                "has no game this week, so that place adds nothing",
                "have no game this week, so those places add nothing",
            )
        )
    if doubts:
        lines.append(
            _pick_line(
                doubts,
                "might not play, which cuts the projected points",
                "might not play, which cuts the projected points",
            )
        )
    if benched:
        lines.append(
            _pick_line(
                benched,
                "has not been starting, so minutes are not expected",
                "have not been starting, so minutes are not expected",
            )
        )
    weakest = _ordered(
        paired,
        highest_first=False,
        include=lambda mark: mark < _STRONG_MARK,
        only_playing=True,
    )
    holding = _holding_line(weakest, bar, sole_reason=not lines)
    if holding:
        lines.append(holding)
    return tuple(line for line in lines if line)


def _lead_strong(starter: StarterOutlook, bar: float, group_size: int) -> str:
    return f"{group_size} starters are strong picks. {_standout(starter, bar)}"


def _standout(starter: StarterOutlook, bar: float) -> str:
    cause = _cause_clause(_lift_causes(starter))
    return (
        f"{_starter_name(starter)} projects {_points(starter.projection)} points{cause}, "
        f"{_gap_phrase(starter.projection, bar, above=True)}"
    )


def _tied_strong(starters: list[StarterOutlook], bar: float) -> str:
    projection = starters[0].projection
    subject, verb = _group_subject(starters)
    return (
        f"{subject} {verb} {_points(projection)} points, "
        f"{_gap_phrase(projection, bar, above=True)}"
    )


def _rest_strong(starters: list[StarterOutlook]) -> str:
    if len(starters) == 1:
        starter = starters[0]
        cause = _cause_clause(_lift_causes(starter))
        return f"{_starter_name(starter)} is a strong pick too, on {_points(starter.projection)} points{cause}"
    lowest = _points(min(starter.projection for starter in starters))
    quantifier = "both" if len(starters) == 2 else "all"
    names = _every_name(starters)
    if names:
        return f"{_join_names(names)} are strong picks too, {quantifier} on at least {lowest} points"
    return f"{len(starters)} more are strong picks too, {quantifier} on at least {lowest} points"


def _holding_line(starters: list[StarterOutlook], bar: float, *, sole_reason: bool) -> str:
    if not starters:
        return ""
    if len(starters) == 1:
        return _finish(_one_drag(starters[0], bar, sole_reason=sole_reason))
    if _same_projected_points(starters):
        return _finish(_tied_short(starters, bar, sole_reason=sole_reason))
    return _finish(_varied_short(starters, bar, sole_reason=sole_reason))


def _one_drag(starter: StarterOutlook, bar: float, *, sole_reason: bool) -> str:
    cause = _drag_cause(starter)
    sentence = (
        f"{_starter_name(starter)} projects {_points(starter.projection)} points"
        f"{_cause_clause([cause] if cause else [])}, "
        f"{_gap_phrase(starter.projection, bar, above=False)}"
    )
    if sole_reason:
        sentence += ". That is what keeps this off a 10"
    return sentence


def _tied_short(starters: list[StarterOutlook], bar: float, sole_reason: bool) -> str:
    projection = starters[0].projection
    cause = _shared_drag_cause(starters)
    subject, verb = _group_subject(starters)
    sentence = (
        f"{subject} {verb} {_points(projection)} points{_cause_clause([cause] if cause else [])}, "
        f"{_gap_phrase(projection, bar, above=False)}"
    )
    if sole_reason:
        sentence += ". That is what keeps this off a 10"
    return sentence


def _varied_short(starters: list[StarterOutlook], bar: float, sole_reason: bool) -> str:
    lead = _join_names([_drag_chip(starter) for starter in starters[:2]])
    rest = starters[2:]
    if rest:
        sentence = f"{lead} are the furthest below the {_points(bar)} points a strong pick needs. {_rest_short(rest)}"
    else:
        sentence = f"{lead} are short of the {_points(bar)} points a strong pick needs"
    if sole_reason:
        sentence += ". That is what keeps this off a 10"
    return sentence


def _rest_short(starters: list[StarterOutlook]) -> str:
    names = _every_name(starters)
    if names is None:
        return f"{len(starters)} more are short of it too"
    if len(names) == 1:
        return f"{names[0]} is short of it too"
    return f"{_join_names(names)} are short of it too"


def _group_subject(starters: list[StarterOutlook]) -> tuple[str, str]:
    if len(starters) == XI_SIZE:
        return "All 11 starters", "project"
    names = _every_name(starters)
    if names:
        return _join_names(names), "each project"
    return f"{len(starters)} starters", "project"


def _drag_chip(starter: StarterOutlook) -> str:
    cause = _drag_cause(starter)
    points = _points(starter.projection)
    if cause:
        return f"{_starter_name(starter)} ({points}, {cause})"
    return f"{_starter_name(starter)} ({points})"


def _starter_name(starter: StarterOutlook) -> str:
    return starter.name or "One starter"


def _same_projected_points(starters: list[StarterOutlook]) -> bool:
    return len({_points(starter.projection) for starter in starters}) == 1


def _every_name(starters: list[StarterOutlook]) -> list[str] | None:
    names = [starter.name for starter in starters]
    if not names or not all(names):
        return None
    return names


def _gap_phrase(projection: float, bar: float, *, above: bool) -> str:
    gap = projection - bar if above else bar - projection
    shown = f"{gap:.1f}"
    target = f"the {_points(bar)} points a strong pick needs"
    if gap <= 0 or shown == "0.0":
        relation = "just above" if above else "just short of"
        return f"{relation} {target}"
    direction = "above" if above else "short of"
    return f"about {shown} {direction} {target}"


def _cause_clause(causes: list[str]) -> str:
    if not causes:
        return ""
    if len(causes) == 1:
        return f", with {causes[0]}"
    return f", with {causes[0]} and {causes[1]}"


def _lift_causes(starter: StarterOutlook) -> list[str]:
    chosen: list[str] = []
    if starter.fixture is not None and starter.fixture >= _EASY_FIXTURE:
        chosen.append("an easy fixture")
    ranked: list[tuple[float, str]] = []
    if starter.xgi is not None and starter.xgi >= _STRONG_XGI:
        ranked.append((starter.xgi, "strong underlying numbers"))
    if starter.form is not None and starter.form >= _STRONG_FORM:
        ranked.append((starter.form, "strong recent form"))
    ranked.sort(key=lambda item: item[0], reverse=True)
    for _, phrase in ranked:
        if len(chosen) == 2:
            break
        chosen.append(phrase)
    return chosen


def _drag_cause(starter: StarterOutlook) -> str:
    ranked: list[tuple[float, str]] = []
    if starter.fixture is not None and starter.fixture <= _HARD_FIXTURE:
        ranked.append((starter.fixture, "a hard fixture"))
    if starter.xgi is not None and starter.xgi <= _WEAK_XGI:
        ranked.append((starter.xgi, "weak underlying numbers"))
    if starter.form is not None and starter.form <= _POOR_FORM:
        ranked.append((starter.form, "poor recent form"))
    if starter.minutes_security is not None and starter.minutes_security <= _SHAKY_MINUTES:
        ranked.append((starter.minutes_security, "minutes that are not secure"))
    if not ranked:
        return ""
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


def _shared_drag_cause(starters: list[StarterOutlook]) -> str:
    causes = [_drag_cause(starter) for starter in starters]
    first = causes[0]
    if first and all(cause == first for cause in causes):
        return first
    return ""


def _points(value: float) -> str:
    return f"{value:.1f}"


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
    chosen.sort(
        key=lambda item: (
            -item[2] if highest_first else item[2],
            -item[1].projection if highest_first else item[1].projection,
            item[0],
        )
    )
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
    return _join_names(cleaned), len(cleaned) == 1


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])} and {names[-1]}"


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
