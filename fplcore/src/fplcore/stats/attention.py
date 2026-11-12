from __future__ import annotations

from typing import Any

from fplcore.constants import INSIGHTS_MIN_MINUTES, STATS_TOP_N
from fplcore.stats.market import player_card

SAMPLE_MATCHES = 4
NAILED_STARTS = 2 / 3
ROTATED_STARTS = 0.5
KIND_RUN = 2.5
NASTY_RUN = 4.0
BLANK_DIFFICULTY = 5.0
_RULED_OUT = frozenset({"i", "s", "u"})
_STATUS_LABEL = {"d": "Doubtful", "i": "Injured", "s": "Suspended", "u": "Unavailable"}


def apply_live_flags(players: list[dict[str, Any]], squad_players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer the flags just fetched for this squad over the stored player row."""
    live = {int(player["element"]): player for player in squad_players}
    updated: list[dict[str, Any]] = []
    for row in players:
        fresh = live.get(int(row["id"]))
        if fresh is None:
            updated.append(row)
            continue
        updated.append(
            {
                **row,
                "status": fresh.get("status") or row.get("status") or "a",
                "chance_of_playing_next_round": fresh.get("chance_of_playing_next_round"),
                "news": fresh.get("news") or "",
            }
        )
    return updated


def squad_attention(
    players: list[dict[str, Any]],
    squad_ids: set[int],
    *,
    recent: dict[int, dict[str, Any]] | None = None,
    gameweeks: list[int],
    fixtures_by_team: dict[int, dict[int, list[dict[str, Any]]]],
) -> dict[str, list[dict[str, Any]]]:
    """Who in this squad needs a decision, and who is secure through a kind run."""
    known = _fixtures_known(gameweeks, fixtures_by_team)
    prepared = _prepare(players, recent or {})
    sort_out: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    leave_alone: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for row in prepared:
        if int(row["id"]) not in squad_ids:
            continue
        look = _look(row, gameweeks, fixtures_by_team, known)
        card = _card(row, look)
        if look.flagged or look.rotated or look.blank or _nasty(look.mean):
            sort_out.append((_urgency(look), card))
            continue
        if look.nailed and _kind(look.mean):
            leave_alone.append(((look.mean or 0, -look.start_rate, row["web_name"]), card))
    sort_out.sort(key=lambda item: item[0])
    leave_alone.sort(key=lambda item: item[0])
    return {
        "sort_out": [card for _, card in sort_out],
        "leave_alone": [card for _, card in leave_alone],
    }


def fixture_runs(
    players: list[dict[str, Any]],
    *,
    recent: dict[int, dict[str, Any]] | None = None,
    gameweeks: list[int],
    fixtures_by_team: dict[int, dict[int, list[dict[str, Any]]]],
    min_minutes: int = INSIGHTS_MIN_MINUTES,
    n: int = STATS_TOP_N,
) -> dict[str, list[dict[str, Any]]]:
    """Kindest and nastiest next three among players who are actually playing."""
    known = _fixtures_known(gameweeks, fixtures_by_team)
    if not known:
        return {"easy": [], "hard": []}
    easy: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    hard: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for row in _prepare(players, recent or {}):
        if not _playing(row, min_minutes):
            continue
        look = _look(row, gameweeks, fixtures_by_team, known)
        if look.mean is None:
            continue
        card = _card(row, look)
        if look.nailed and not look.flagged and not look.blank and _kind(look.mean):
            easy.append(((look.mean, row["web_name"]), card))
        elif _nasty(look.mean):
            hard.append(((-look.mean, row["web_name"]), card))
    easy.sort(key=lambda item: item[0])
    hard.sort(key=lambda item: item[0])
    return {"easy": [card for _, card in easy[:n]], "hard": [card for _, card in hard[:n]]}


def _prepare(players: list[dict[str, Any]], recent: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in players:
        extra = recent.get(int(row["id"]))
        if not extra:
            prepared.append(row)
            continue
        prepared.append(
            {
                **row,
                "recent_starts": int(extra.get("recent_starts") or 0),
                "recent_matches": int(extra.get("recent_matches") or 0),
                "recent_minutes": int(extra.get("recent_minutes") or 0),
            }
        )
    return prepared


def _playing(row: dict[str, Any], min_minutes: int) -> bool:
    recent = row.get("recent_minutes")
    minutes = int(recent if recent is not None else row.get("minutes") or 0)
    return minutes >= min_minutes


def _fixtures_known(
    gameweeks: list[int], fixtures_by_team: dict[int, dict[int, list[dict[str, Any]]]]
) -> bool:
    if not gameweeks:
        return False
    return any(weeks.get(gw) for weeks in fixtures_by_team.values() for gw in gameweeks)


def _weeks(
    team_id: int,
    gameweeks: list[int],
    fixtures_by_team: dict[int, dict[int, list[dict[str, Any]]]],
) -> list[list[dict[str, Any]]]:
    team = fixtures_by_team.get(team_id, {})
    return [list(team.get(gw, [])) for gw in gameweeks]


def _mean(weeks: list[list[dict[str, Any]]]) -> float:
    scores: list[float] = []
    for week in weeks:
        if not week:
            scores.append(BLANK_DIFFICULTY)
            continue
        scores.append(sum(int(match["fdr"]) for match in week) / len(week))
    return sum(scores) / len(scores)


def _kind(mean: float | None) -> bool:
    return mean is not None and mean <= KIND_RUN


def _nasty(mean: float | None) -> bool:
    return mean is not None and mean >= NASTY_RUN


class _Look:
    def __init__(
        self,
        *,
        flagged: bool,
        ruled_out: bool,
        chance: int | None,
        rotated: bool,
        nailed: bool,
        blank: bool,
        mean: float | None,
        start_rate: float,
        detail: str,
        run: str,
    ) -> None:
        self.flagged = flagged
        self.ruled_out = ruled_out
        self.chance = chance
        self.rotated = rotated
        self.nailed = nailed
        self.blank = blank
        self.mean = mean
        self.start_rate = start_rate
        self.detail = detail
        self.run = run


def _look(
    row: dict[str, Any],
    gameweeks: list[int],
    fixtures_by_team: dict[int, dict[int, list[dict[str, Any]]]],
    known: bool,
) -> _Look:
    status = str(row.get("status") or "a")
    chance = _chance(row)
    flagged = status != "a" or (chance is not None and chance < 100)
    starts, matches = _starts(row)
    start_rate = starts / matches if matches else 0.0
    sampled = matches >= SAMPLE_MATCHES
    weeks = _weeks(int(row["team_id"]), gameweeks, fixtures_by_team) if known else None
    blank = bool(weeks) and any(not week for week in weeks or [])
    mean = _mean(weeks) if weeks else None
    detail = _detail(_flag_line(status, chance, row.get("news")), _start_line(starts, matches), blank)
    return _Look(
        flagged=flagged,
        ruled_out=status in _RULED_OUT,
        chance=chance,
        rotated=sampled and start_rate <= ROTATED_STARTS,
        nailed=sampled and start_rate >= NAILED_STARTS,
        blank=blank,
        mean=mean,
        start_rate=start_rate,
        detail=detail,
        run=_run_text(weeks),
    )


def _card(row: dict[str, Any], look: _Look) -> dict[str, Any]:
    return player_card(row, {"detail": look.detail, "run": look.run})


def _urgency(look: _Look) -> tuple[Any, ...]:
    chance = look.chance if look.chance is not None else (0 if look.flagged else 100)
    return (
        0 if look.flagged else 1,
        chance,
        0 if look.blank else 1,
        0 if look.rotated else 1,
        -(look.mean or 0),
    )


def _chance(row: dict[str, Any]) -> int | None:
    raw = row.get("chance_of_playing_next_round")
    if raw is None:
        return None
    return int(raw)


def _starts(row: dict[str, Any]) -> tuple[int, int]:
    matches = int(row.get("recent_matches") or 0)
    starts = int(row.get("recent_starts") or 0)
    if matches and starts > matches:
        starts = matches
    return starts, matches


def _flag_line(status: str, chance: int | None, news: Any) -> str | None:
    flagged = status != "a" or (chance is not None and chance < 100)
    if not flagged:
        return None
    text = _sentence(str(news or ""))
    if text:
        return text
    if status == "a" and chance is not None:
        return f"{chance}% chance of playing."
    label = _STATUS_LABEL.get(status, "Flagged")
    if chance is not None and chance < 100:
        return f"{label}, {chance}%."
    return f"{label}."


def _start_line(starts: int, matches: int) -> str | None:
    if matches < SAMPLE_MATCHES:
        return None
    return f"Started {starts} of the last {matches}."


def _detail(flag: str | None, starts: str | None, blank: bool) -> str:
    parts = [part for part in (flag, starts, "No game in the next three." if blank else None) if part]
    return " ".join(parts)


def _sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) > 110:
        cut = cleaned[:110].rsplit(" ", 1)[0]
        cleaned = (cut or cleaned[:110]).rstrip(".,; ") + "…"
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?…":
        return cleaned
    return f"{cleaned}."


def _run_text(weeks: list[list[dict[str, Any]]] | None) -> str:
    if not weeks:
        return ""
    parts: list[str] = []
    for week in weeks:
        if not week:
            parts.append("Blank")
            continue
        parts.append(" & ".join(_chip(match) for match in week))
    return " · ".join(parts)


def _chip(match: dict[str, Any]) -> str:
    side = "H" if match["is_home"] else "A"
    return f"{side} {match['opponent']} ({int(match['fdr'])})"
