from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.chat.tools.common import ok
from api.chat.tools.shape import compact_player
from api.services import ranked_players
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str | None = None
    position_id: int | None = Field(default=None, ge=1, le=4)
    team_id: int | None = None
    max_cost_m: float | None = None
    limit: int | None = Field(default=None, ge=1, le=8)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = SearchArgs.model_validate(args.model_dump())
    weights = ctx.weights or DEFAULT_WEIGHTS
    max_cost = None if parsed.max_cost_m is None else int(round(parsed.max_cost_m * 10))
    rows = ranked_players(
        conn,
        weights=weights,
        position=parsed.position_id,
        team=parsed.team_id,
        max_cost=max_cost,
        horizon=1,
    )
    query = (parsed.query or "").casefold()
    if query:
        rows = [row for row in rows if query in str(row["web_name"]).casefold()]
    limit = parsed.limit or 8
    data = [compact_player(row) for row in rows[:limit]]
    if not data:
        return failure("NO_MATCH", "No player matched that search.", hint="Try a shorter name.")
    return ok({"players": data}, as_of=None, data_version=ctx.data_version)


search_players = BoundTool(
    name="search_players",
    description="Search the player list by name, position, club or max price in £m. Returns projected points for the next gameweek.",
    args_model=SearchArgs,
    handler=_run,
)
