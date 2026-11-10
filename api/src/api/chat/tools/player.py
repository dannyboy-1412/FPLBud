from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from api.chat.context import pounds
from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of, matches_by_team, with_matches
from api.services import player_detail, ranked_players
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS, POSITION_SHORT
from fplcore.db.repos import current_season_id
from fplcore.db.stats_repo import fixtures_for, next_gw_id

Horizon = Literal[1, 2, 3, 4, 5]


class PlayerArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: int
    horizon: Horizon = 1


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = PlayerArgs.model_validate(args.model_dump())
    detail = player_detail(conn, parsed.player_id)
    if detail is None:
        return failure("NOT_FOUND", "No player with that id.", hint="Use search_players.")
    player = detail["player"]
    ranked = {
        int(row["id"]): row
        for row in ranked_players(conn, weights=ctx.weights or DEFAULT_WEIGHTS, horizon=parsed.horizon)
    }
    row = ranked.get(int(player["id"]), {})
    by_gw = _with_fixtures(conn, int(player["team_id"]), list(row.get("by_gw") or []), parsed.horizon)
    history = [
        {
            "round": item.get("round"),
            "points": item.get("total_points"),
            "minutes": item.get("minutes"),
            "xg": _float(item.get("expected_goals")),
            "xa": _float(item.get("expected_assists")),
        }
        for item in list(detail["history"])[:5]
    ]
    return ok(
        {
            "id": int(player["id"]),
            "name": player["web_name"],
            "team": player.get("team_short"),
            "position": POSITION_SHORT.get(int(player["position_id"]), "?"),
            "price_m": pounds(player.get("now_cost")),
            "own": float(player["selected_by_percent"]),
            "status": player.get("status"),
            "chance": player.get("chance_of_playing_next_round"),
            "news": player.get("news") or "",
            "proj": row.get("proj"),
            "by_gw": by_gw,
            "recent": history,
        },
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
    )


def _with_fixtures(conn: Any, team_id: int, by_gw: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    try:
        season = current_season_id(conn)
        start = next_gw_id(conn, season)
    except RuntimeError:
        return by_gw[:horizon]
    rows = fixtures_for(conn, season, [start + offset for offset in range(horizon)], team_id)
    return with_matches(by_gw[:horizon], team_id, matches_by_team(rows))


def _float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


get_player = BoundTool(
    name="get_player",
    description=(
        "One player's price, status, news, last few matches, and projections over 1 to 5 gameweeks. "
        "Not a season record by fixture difficulty."
    ),
    args_model=PlayerArgs,
    handler=_run,
)
