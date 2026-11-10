from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of
from api.chat.tools.shape import compact_player
from api.services import ranked_players
from fplcore.chat.names import fold
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS

Horizon = Literal[1, 2, 3, 4, 5]
SortKey = Literal["proj", "price", "ownership", "form"]


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str | None = None
    position_id: int | None = Field(default=None, ge=1, le=4)
    team_id: int | None = None
    max_cost_m: float | None = None
    limit: int | None = Field(default=None, ge=1, le=8)
    horizon: Horizon = 1
    sort: SortKey = "proj"


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
        horizon=parsed.horizon,
    )
    query = fold(parsed.query or "")
    if query:
        rows = [row for row in rows if _matches(row, query)]
    rows = sorted(rows, key=lambda row: _sort_value(row, parsed.sort), reverse=True)
    data = []
    for row in rows[: parsed.limit or 8]:
        item = compact_player(row)
        item["form"] = row.get("form")
        data.append(item)
    if not data:
        return failure("NO_MATCH", "No player matched that search.", hint="Try a shorter name.")
    return ok({"players": data}, as_of=lookup_as_of(conn), data_version=ctx.data_version)


def _matches(row: dict[str, Any], query: str) -> bool:
    fields = [
        fold(str(row.get("web_name") or "")),
        fold(str(row.get("first_name") or "")),
        fold(str(row.get("second_name") or "")),
        fold(f"{row.get('first_name') or ''} {row.get('second_name') or ''}"),
    ]
    return any(query in field for field in fields if field)


def _sort_value(row: dict[str, Any], sort: str) -> float:
    if sort == "price":
        return float(row.get("now_cost") or 0)
    if sort == "ownership":
        return float(row.get("selected_by_percent") or 0)
    if sort == "form":
        return float(row.get("form") or 0)
    return float(row.get("proj") or 0)


search_players = BoundTool(
    name="search_players",
    description="Search by name, position, club or max price in £m. Matches accents and surnames. Sort by proj, price, ownership or form.",
    args_model=SearchArgs,
    handler=_run,
)
