from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from api.chat.context import pounds
from api.chat.tools.common import ok
from api.services import player_detail, ranked_players
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS, POSITION_SHORT


class PlayerArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: int


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = PlayerArgs.model_validate(args.model_dump())
    detail = player_detail(conn, parsed.player_id)
    if detail is None:
        return failure("NOT_FOUND", "No player with that id.", hint="Use search_players.")
    player = detail["player"]
    ranked = {
        int(row["id"]): row
        for row in ranked_players(conn, weights=ctx.weights or DEFAULT_WEIGHTS, horizon=1)
    }
    proj = ranked.get(int(player["id"]), {}).get("proj")
    history = [
        {"round": row.get("round"), "points": row.get("total_points"), "minutes": row.get("minutes")}
        for row in list(detail["history"])[:5]
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
            "proj": proj,
            "recent": history,
        },
        as_of=None,
        data_version=ctx.data_version,
    )


get_player = BoundTool(
    name="get_player",
    description="One player's price, status, news, recent points and next-gameweek projection.",
    args_model=PlayerArgs,
    handler=_run,
)
