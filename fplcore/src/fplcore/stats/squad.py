from __future__ import annotations

from typing import Any

from fplcore.constants import DIFFERENTIAL_OWNERSHIP, STATS_TOP_N, TEMPLATE_OWNERSHIP
from fplcore.stats.market import player_card


def captaincy_board(
    starters: list[dict[str, Any]],
    crowd: dict[str, Any] | None,
) -> dict[str, Any]:
    ranked = sorted(starters, key=lambda p: float(p["proj"]), reverse=True)
    gap = 0.0
    if len(ranked) >= 2:
        gap = float(ranked[0]["proj"]) - float(ranked[1]["proj"])
    return {"board": ranked, "gap": round(gap, 2), "crowd": crowd}


def template_threats(
    ranked: list[dict[str, Any]],
    squad_ids: set[int],
    *,
    min_ownership: float = TEMPLATE_OWNERSHIP,
    n: int = STATS_TOP_N,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for player in ranked:
        if int(player["id"]) in squad_ids:
            continue
        own = float(player["selected_by_percent"])
        if own < min_ownership:
            continue
        proj = float(player["proj"])
        rows.append(
            player_card(
                player,
                {"proj": round(proj, 2), "threat": round(own * proj, 2)},
            )
        )
    rows.sort(key=lambda r: float(r["threat"]), reverse=True)
    return rows[:n]


def squad_differentials(
    ranked: list[dict[str, Any]],
    squad_ids: set[int],
    *,
    max_ownership: float = DIFFERENTIAL_OWNERSHIP,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for player in ranked:
        if int(player["id"]) not in squad_ids:
            continue
        own = float(player["selected_by_percent"])
        if own >= max_ownership:
            continue
        rows.append(player_card(player, {"proj": round(float(player["proj"]), 2)}))
    rows.sort(key=lambda r: float(r["proj"]), reverse=True)
    return rows


def ownership_profile(
    squad: list[dict[str, Any]],
    starter_ids: set[int],
    *,
    template_cut: float = TEMPLATE_OWNERSHIP,
    differential_cut: float = DIFFERENTIAL_OWNERSHIP,
) -> dict[str, Any]:
    xi = [p for p in squad if int(p["id"]) in starter_ids]
    xi_own = [float(p["selected_by_percent"]) for p in xi]
    owns = [float(p["selected_by_percent"]) for p in squad]
    return {
        "xi_avg_ownership": round(sum(xi_own) / len(xi_own), 1) if xi_own else 0.0,
        "template_count": sum(1 for own in owns if own >= template_cut),
        "differential_count": sum(1 for own in owns if own < differential_cut),
        "squad_size": len(squad),
    }
