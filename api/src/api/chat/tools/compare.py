from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.chat.tools.common import ok
from api.chat.tools.shape import compact_player
from api.services import ranked_players
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS


class CompareArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_ids: list[int] = Field(min_length=2, max_length=3)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = CompareArgs.model_validate(args.model_dump())
    wanted = set(parsed.player_ids)
    rows = [
        row
        for row in ranked_players(conn, weights=ctx.weights or DEFAULT_WEIGHTS, horizon=1)
        if int(row["id"]) in wanted
    ]
    if len(rows) < 2:
        return failure("NOT_FOUND", "Need at least two known players.", hint="Use search_players for the ids.")
    return ok(
        {"players": [compact_player(row) for row in rows]},
        as_of=None,
        data_version=ctx.data_version,
    )


compare_players = BoundTool(
    name="compare_players",
    description="Compare two or three players on price, ownership and next-gameweek projection.",
    args_model=CompareArgs,
    handler=_run,
)
