from __future__ import annotations

from typing import Any

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


def combined_scores_by_id(
    xi_ids: list[int],
    rows_by_id: dict[int, dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> dict[int, float]:
    out: dict[int, float] = {}
    for pid in xi_ids:
        row = rows_by_id.get(pid)
        out[pid] = combined_score(scores_from_metric_row(row), weights) if row else 0.0
    return out


def squad_score_for_xi(xi_ids: list[int], scores_by_id: dict[int, float]) -> float:
    values = [float(scores_by_id.get(pid, 0.0)) for pid in xi_ids[:XI_SIZE]]
    values.extend([0.0] * (XI_SIZE - len(values)))
    return round(sum(values) / XI_SIZE * 100, 1)


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
        proj = projected_points(
            score=combined_score(scores_from_metric_row(row), weights),
            fixture_count=int(row.get("fixture_count") or 0),
            avail=availability(
                chance_of_playing_next_round=row.get("chance_of_playing_next_round"),
                status=str(row.get("status") or "a"),
                k=1,
            ),
        )
        rounded = round(proj, 2)
        players.append({"id": pid, "web_name": row["web_name"], "proj": rounded})
        total += proj
    players.sort(key=lambda p: float(p["proj"]), reverse=True)
    return {"total": round(total, 1), "players": players}


def performing_players(recent: list[dict[str, Any]], squad_ids: set[int]) -> list[dict[str, Any]]:
    scoped = [row for row in recent if int(row["id"]) in squad_ids]
    return in_form(scoped, n=REPORT_TOP_N)


def underperforming_players(players: list[dict[str, Any]], squad_ids: set[int]) -> list[dict[str, Any]]:
    scoped = [row for row in players if int(row["id"]) in squad_ids]
    return finishing_variance(scoped, n=REPORT_TOP_N)["underperformers"]
