from __future__ import annotations

from typing import Any

from fplcore.constants import SQUAD_SCORE_HIGH_PERCENTILE, SQUAD_SCORE_LOW_PERCENTILE
from fplcore.metrics.combine import availability, combined_score, projected_points
from fplcore.stats.insights import finishing_variance, in_form

XI_SIZE = 11
REPORT_TOP_N = 5
SCORE_KEYS = ("form", "fixture", "home", "xgi", "value", "minutes", "trend")


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
    return projected_points(
        score=combined_score(scores_from_metric_row(row), weights),
        fixture_count=int(row.get("fixture_count") or 0),
        avail=availability(
            chance_of_playing_next_round=row.get("chance_of_playing_next_round"),
            status=str(row.get("status") or "a"),
            k=1,
        ),
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
    return finishing_variance(scoped, n=REPORT_TOP_N)["underperformers"]


def overperforming_players(players: list[dict[str, Any]], squad_ids: set[int]) -> list[dict[str, Any]]:
    scoped = [row for row in players if int(row["id"]) in squad_ids]
    return finishing_variance(scoped, n=REPORT_TOP_N)["overperformers"]
