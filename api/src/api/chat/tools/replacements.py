"""Ranked replacements for one squad player."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.chat.context import pounds
from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of, matches_by_team, no_team, user_snapshot
from api.services import load_opt_players
from fplcore.chat.moves import Candidate, rank_replacements
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import current_season_id
from fplcore.db.stats_repo import fixtures_for, next_gw_id
from fplcore.optimise import PlayerOpt
from fplcore.rules import SquadSlot


class ReplacementArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    out_player_id: int
    horizon: Literal[1, 3, 5]
    max_price_m: float | None = None
    limit: int | None = Field(default=None, ge=1, le=5)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = ReplacementArgs.model_validate(args.model_dump())
    snapshot = user_snapshot(ctx, conn)
    if snapshot is None:
        return no_team()
    opts = load_opt_players(conn, snapshot, ctx.weights or DEFAULT_WEIGHTS, parsed.horizon)
    by_id = {player.id: player for player in opts}
    outgoing = by_id.get(parsed.out_player_id)
    if outgoing is None or not outgoing.in_squad:
        return failure("NOT_FOUND", "That player is not in the squad.", hint="Use get_my_team for the ids.")
    teams = _team_names(conn, snapshot.season_id)
    limit = parsed.limit or 5
    cap = None if parsed.max_price_m is None else int(round(parsed.max_price_m * 10))
    ranked = rank_replacements(
        parsed.out_player_id,
        _slots(opts),
        [_candidate(player, teams) for player in opts],
        out_proj=_sum(outgoing),
        bank=int(snapshot.bank),
        max_price_tenths=cap,
        limit=limit,
    )
    if not ranked.owned:
        return failure("NOT_FOUND", "That player is not in the squad.", hint="Use get_my_team for the ids.")
    fixtures = _next_fixtures(conn, snapshot.season_id)
    details = _details(conn, snapshot.season_id, [item.candidate.player_id for item in ranked.ranked])
    players = []
    for item in ranked.ranked:
        player = item.candidate
        extra = details.get(player.player_id, {})
        players.append(
            {
                "id": player.player_id,
                "name": player.name,
                "team": player.team,
                "price_m": pounds(player.cost),
                "proj": player.proj,
                "delta_vs_out": item.delta,
                "own": extra.get("own", 0.0),
                "status": extra.get("status", player.status),
                "fixtures": fixtures.get(player.team_id, [])[:3],
            }
        )
    notes = [ranked.note] if ranked.note else []
    return ok(
        {"budget_m": pounds(ranked.budget_tenths), "players": players, "note": ranked.note},
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
        notes=notes,
    )


def _slots(players: list[PlayerOpt]) -> list[SquadSlot]:
    return [
        SquadSlot(player.id, player.position_id, player.team_id, player.sell)
        for player in players
        if player.in_squad
    ]


def _candidate(player: PlayerOpt, teams: dict[int, str]) -> Candidate:
    return Candidate(
        player_id=player.id,
        name=player.web_name,
        team_id=player.team_id,
        team=teams.get(player.team_id, ""),
        position_id=player.position_id,
        cost=player.cost,
        proj=_sum(player),
        own=0.0,
        status="a" if player.can_in or player.in_squad else "u",
        can_in=player.can_in,
    )


def _sum(player: PlayerOpt) -> float:
    return round(sum(player.proj), 2)


def _details(conn: Any, season_id: str, ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    rows = conn.execute(
        """
        select id, status, selected_by_percent
          from players
         where season_id = %s and id = any(%s)
        """,
        [season_id, ids],
    ).fetchall()
    return {
        int(row["id"]): {"status": row["status"], "own": float(row["selected_by_percent"])}
        for row in rows
    }


def _team_names(conn: Any, season_id: str) -> dict[int, str]:
    rows = conn.execute(
        "select id, short_name from teams where season_id = %s",
        [season_id],
    ).fetchall()
    return {int(row["id"]): str(row["short_name"]) for row in rows}


def _next_fixtures(conn: Any, season_id: str) -> dict[int, list[dict[str, Any]]]:
    try:
        season = season_id or current_season_id(conn)
        start = next_gw_id(conn, season)
    except RuntimeError:
        return {}
    rows = fixtures_for(conn, season, [start, start + 1, start + 2])
    grouped = matches_by_team(rows)
    return {
        team_id: [match for gw in sorted(by_gw) for match in by_gw[gw]]
        for team_id, by_gw in grouped.items()
    }


find_replacements = BoundTool(
    name="find_replacements",
    description="Best affordable replacements for one squad player over 1, 3 or 5 gameweeks, already ranked by projected gain.",
    args_model=ReplacementArgs,
    handler=_run,
)
