"""One-call squad review. Lists stay short so the answer does not need more tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from api.chat.tools.common import NoArgs, ok
from api.chat.tools.lineup import lineup_payload
from api.chat.tools.reading import lookup_as_of, matches_by_team, no_team, user_snapshot
from api.services import compute_squad_score, load_opt_players, squad_stats_payload
from fplcore.chat.moves import Candidate, rank_replacements
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import current_season_id
from fplcore.db.stats_repo import fixtures_for, next_gw_id
from fplcore.optimise import PlayerOpt
from fplcore.rules import SquadSlot
from fplcore.team_import import TeamSnapshot


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    del args
    snapshot = user_snapshot(ctx, conn)
    if snapshot is None:
        return no_team()
    snapshot.squad_players = [
        {"element": int(pick["element"]), "position": int(pick.get("position") or 0)}
        for pick in snapshot.picks
    ]
    score = compute_squad_score(conn, snapshot)
    weights = ctx.weights or DEFAULT_WEIGHTS
    stats = squad_stats_payload(conn, {"picks": snapshot.picks}, weights)
    opts = load_opt_players(conn, snapshot, weights, 3)
    by_id = {player.id: player for player in opts}
    lineup = lineup_payload(ctx, conn)
    changes = lineup.get("changes_vs_current", []) if isinstance(lineup, dict) else []
    return ok(
        {
            "squad_score": score.value,
            "flags": list(snapshot.flags)[:3],
            "exposure": _exposure(conn, snapshot, by_id),
            "weakest": _weakest(snapshot, by_id, opts),
            "bench_problems": list(changes)[:3],
            "template_threats": _threats(stats.get("template_threats")),
        },
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
        notes=["Squad score uses the same 0-10 scale as the dashboard."],
    )


def _weakest(
    snapshot: TeamSnapshot,
    by_id: dict[int, PlayerOpt],
    opts: list[PlayerOpt],
) -> list[dict[str, Any]]:
    starters = [
        int(pick["element"])
        for pick in snapshot.picks
        if int(pick.get("position") or 99) <= 11 and int(pick["element"]) in by_id
    ]
    starters.sort(key=lambda player_id: by_id[player_id].proj[0] if by_id[player_id].proj else 0.0)
    slots = [
        SquadSlot(player.id, player.position_id, player.team_id, player.sell)
        for player in opts
        if player.in_squad
    ]
    candidates = [_candidate(player) for player in opts]
    weakest: list[dict[str, Any]] = []
    for player_id in starters[:2]:
        outgoing = by_id[player_id]
        ranked = rank_replacements(
            player_id,
            slots,
            candidates,
            out_proj=round(sum(outgoing.proj), 2),
            bank=int(snapshot.bank),
            max_price_tenths=None,
            limit=1,
        )
        best = ranked.ranked[0] if ranked.ranked else None
        weakest.append(
            {
                "id": player_id,
                "name": outgoing.web_name,
                "proj": round(sum(outgoing.proj), 2),
                "replacement_id": best.candidate.player_id if best else None,
                "replacement_name": best.candidate.name if best else None,
                "delta": best.delta if best else None,
                "note": ranked.note,
            }
        )
    return weakest


def _candidate(player: PlayerOpt) -> Candidate:
    return Candidate(
        player_id=player.id,
        name=player.web_name,
        team_id=player.team_id,
        team="",
        position_id=player.position_id,
        cost=player.cost,
        proj=round(sum(player.proj), 2),
        own=0.0,
        status="a",
        can_in=player.can_in,
    )


def _exposure(conn: Any, snapshot: TeamSnapshot, by_id: dict[int, PlayerOpt]) -> list[dict[str, Any]]:
    try:
        season = snapshot.season_id or current_season_id(conn)
        start = next_gw_id(conn, season)
    except RuntimeError:
        return []
    window = [start, start + 1, start + 2]
    fixtures = matches_by_team(fixtures_for(conn, season, window))
    starter_teams = [
        by_id[int(pick["element"])].team_id
        for pick in snapshot.picks
        if int(pick.get("position") or 99) <= 11 and int(pick["element"]) in by_id
    ]
    counts: list[dict[str, Any]] = []
    for gw in window:
        blanking = 0
        doubling = 0
        for team_id in starter_teams:
            played = len(fixtures.get(team_id, {}).get(gw, []))
            if played == 0:
                blanking += 1
            elif played > 1:
                doubling += 1
        counts.append({"gw": gw, "blanking": blanking, "doubling": doubling})
    return counts


def _threats(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    threats: list[dict[str, Any]] = []
    for item in raw[:3]:
        if not isinstance(item, dict):
            continue
        threats.append(
            {
                "id": item.get("id"),
                "name": item.get("web_name"),
                "proj": item.get("proj"),
                "own": item.get("selected_by_percent"),
            }
        )
    return threats


review_my_squad = BoundTool(
    name="review_my_squad",
    description="Squad score, flags, blank and double exposure, the two weakest starters with one replacement each, and bench changes.",
    args_model=NoArgs,
    handler=_run,
    timeout_s=15.0,
)
