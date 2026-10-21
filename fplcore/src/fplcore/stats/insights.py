from __future__ import annotations

from collections import defaultdict
from typing import Any

from fplcore.constants import (
    DC_THRESHOLD,
    DIFFERENTIAL_OWNERSHIP,
    INSIGHTS_MIN_MINUTES,
    STATS_TOP_N,
)
from fplcore.stats.market import player_card


def _enough_minutes(row: dict[str, Any], *, min_minutes: int) -> bool:
    recent = row.get("recent_minutes")
    minutes = int(recent if recent is not None else row.get("minutes") or 0)
    return minutes >= min_minutes


def in_form(
    recent: list[dict[str, Any]],
    *,
    min_minutes: int = INSIGHTS_MIN_MINUTES,
    n: int = STATS_TOP_N,
) -> list[dict[str, Any]]:
    eligible = [r for r in recent if _enough_minutes(r, min_minutes=min_minutes)]
    eligible.sort(key=lambda r: int(r["recent_points"]), reverse=True)
    out: list[dict[str, Any]] = []
    for row in eligible[:n]:
        mins = max(int(row["recent_minutes"]), 1)
        out.append(
            player_card(
                row,
                {
                    "recent_points": int(row["recent_points"]),
                    "form": float(row["form"]),
                    "xgi90": round(float(row["recent_xgi"]) * 90 / mins, 2),
                },
            )
        )
    return out


def finishing_variance(
    players: list[dict[str, Any]],
    *,
    min_minutes: int = INSIGHTS_MIN_MINUTES,
    n: int = STATS_TOP_N,
) -> dict[str, list[dict[str, Any]]]:
    scored: list[dict[str, Any]] = []
    for row in players:
        if int(row.get("minutes") or 0) < min_minutes:
            continue
        goals = int(row["goals_scored"])
        assists = int(row["assists"])
        xgi = float(row["expected_goal_involvements"])
        xg = float(row["expected_goals"])
        involvements = goals + assists
        scored.append(
            player_card(
                row,
                {
                    "goals": goals,
                    "assists": assists,
                    "xg": round(xg, 2),
                    "xgi": round(xgi, 2),
                    "xgi_delta": round(xgi - involvements, 2),
                    "xg_delta": round(xg - goals, 2),
                },
            )
        )
    under = sorted(scored, key=lambda r: float(r["xgi_delta"]), reverse=True)[:n]
    over = sorted(scored, key=lambda r: float(r["xgi_delta"]))[:n]
    return {"underperformers": under, "overperformers": over}


def differentials(
    ranked: list[dict[str, Any]],
    *,
    max_ownership: float = DIFFERENTIAL_OWNERSHIP,
    n: int = STATS_TOP_N,
) -> list[dict[str, Any]]:
    rows = [
        player_card(p, {"proj": round(float(p["proj"]), 2)})
        for p in ranked
        if float(p["selected_by_percent"]) < max_ownership
    ]
    rows.sort(key=lambda r: float(r["proj"]), reverse=True)
    return rows[:n]


def defensive_leaders(
    recent: list[dict[str, Any]],
    *,
    min_minutes: int = INSIGHTS_MIN_MINUTES,
    n: int = STATS_TOP_N,
) -> list[dict[str, Any]]:
    eligible = [
        r
        for r in recent
        if int(r["position_id"]) in DC_THRESHOLD and _enough_minutes(r, min_minutes=min_minutes)
    ]
    out: list[dict[str, Any]] = []
    for row in eligible:
        mins = max(int(row["recent_minutes"]), 1)
        starts = int(row["dc_starts"])
        hits = int(row["dc_hits"])
        out.append(
            player_card(
                row,
                {
                    "dc_per_90": round(float(row["recent_dc"]) * 90 / mins, 2),
                    "hit_rate": round(hits / starts, 3) if starts else 0.0,
                    "threshold": DC_THRESHOLD[int(row["position_id"])],
                    "dc_hits": hits,
                    "dc_starts": starts,
                },
            )
        )
    out.sort(key=lambda r: (float(r["hit_rate"]), float(r["dc_per_90"])), reverse=True)
    return out[:n]


def bonus_leaders(
    players: list[dict[str, Any]],
    *,
    min_minutes: int = INSIGHTS_MIN_MINUTES,
    n: int = STATS_TOP_N,
) -> list[dict[str, Any]]:
    eligible = [p for p in players if int(p.get("minutes") or 0) >= min_minutes]
    out: list[dict[str, Any]] = []
    for row in eligible:
        mins = max(int(row["minutes"]), 1)
        starts = max(int(row["starts"]), 1)
        out.append(
            player_card(
                row,
                {
                    "bonus": int(row["bonus"]),
                    "bps90": round(int(row["bps"]) * 90 / mins, 1),
                    "bonus_per_start": round(int(row["bonus"]) / starts, 2),
                },
            )
        )
    out.sort(key=lambda r: (int(r["bonus"]), float(r["bps90"])), reverse=True)
    return out[:n]


def set_piece_takers(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_team: dict[tuple[int, str], dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"penalties": [], "corners": [], "freekicks": []}
    )
    for row in players:
        key = (int(row["team_id"]), str(row["team_short"]))
        card = {"id": int(row["id"]), "web_name": row["web_name"]}
        if row.get("penalties_order") is not None:
            by_team[key]["penalties"].append({**card, "order": int(row["penalties_order"])})
        if row.get("corners_and_indirect_freekicks_order") is not None:
            by_team[key]["corners"].append(
                {**card, "order": int(row["corners_and_indirect_freekicks_order"])}
            )
        if row.get("direct_freekicks_order") is not None:
            by_team[key]["freekicks"].append({**card, "order": int(row["direct_freekicks_order"])})

    teams: list[dict[str, Any]] = []
    for (team_id, team_short), buckets in by_team.items():
        for kind in buckets:
            buckets[kind].sort(key=lambda p: int(p["order"]))
            buckets[kind] = buckets[kind][:2]
        if not any(buckets.values()):
            continue
        teams.append({"team_id": team_id, "team_short": team_short, **buckets})
    teams.sort(key=lambda t: t["team_short"])
    return teams
