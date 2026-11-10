from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.chat.context import pounds
from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of, matches_by_team, with_matches
from api.services import ranked_players
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import current_season_id
from fplcore.db.stats_repo import fixtures_for, next_gw_id

Horizon = Literal[1, 2, 3, 4, 5]


class CompareArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_ids: list[int] = Field(min_length=2, max_length=3)
    horizon: Horizon = 1


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = CompareArgs.model_validate(args.model_dump())
    wanted = set(parsed.player_ids)
    rows = [
        row
        for row in ranked_players(conn, weights=ctx.weights or DEFAULT_WEIGHTS, horizon=parsed.horizon)
        if int(row["id"]) in wanted
    ]
    if len(rows) < 2:
        return failure("NOT_FOUND", "Need at least two known players.", hint="Use search_players for the ids.")
    lookup = _fixtures(conn, parsed.horizon)
    return ok(
        {"players": [_player(row, lookup, parsed.horizon) for row in rows]},
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
    )


def _player(row: dict[str, Any], lookup: dict[int, dict[int, list[dict[str, Any]]]], horizon: int) -> dict[str, Any]:
    scores = row.get("scores") if isinstance(row.get("scores"), dict) else {}
    return {
        "id": int(row["id"]),
        "name": row.get("web_name"),
        "team": row.get("team_short"),
        "position_id": row.get("position_id"),
        "price_m": pounds(row.get("now_cost")),
        "own": row.get("selected_by_percent"),
        "status": row.get("status"),
        "proj": row.get("proj"),
        "form": scores.get("form"),
        "fixture": scores.get("fixture"),
        "xgi": scores.get("xgi"),
        "minutes": scores.get("minutes"),
        "by_gw": with_matches(list(row.get("by_gw") or [])[:horizon], int(row["team_id"]), lookup),
    }


def _fixtures(conn: Any, horizon: int) -> dict[int, dict[int, list[dict[str, Any]]]]:
    try:
        season = current_season_id(conn)
        start = next_gw_id(conn, season)
    except RuntimeError:
        return {}
    rows = fixtures_for(conn, season, [start + offset for offset in range(horizon)])
    return matches_by_team(rows)


compare_players = BoundTool(
    name="compare_players",
    description="Compare two or three players over a horizon, with per-gameweek projections, fixtures and component scores.",
    args_model=CompareArgs,
    handler=_run,
)
