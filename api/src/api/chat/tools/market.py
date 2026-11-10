from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of
from api.chat.tools.shape import take
from api.services import market_payload
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult
from fplcore.constants import PRICE_PRESSURE_CAVEAT

MarketKind = Literal[
    "top_in",
    "top_out",
    "risers",
    "fallers",
    "movers_24h",
    "likely_to_rise",
    "likely_to_fall",
]


class MarketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: MarketKind | None = None


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = MarketArgs.model_validate(args.model_dump())
    payload = market_payload(conn)
    keys = (parsed.kind,) if parsed.kind else ("top_in", "top_out", "risers", "fallers")
    data = {key: take(list(payload.get(key) or []), 5) for key in keys}
    return ok(
        {**data, "caveat": payload.get("caveat") or PRICE_PRESSURE_CAVEAT},
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
        notes=["Price lists are pressure, not confirmed changes."],
    )


get_market_movers = BoundTool(
    name="get_market_movers",
    description="Who is being transferred in or out, and who is flagged to rise or fall. Not a confirmed price change.",
    args_model=MarketArgs,
    handler=_run,
)
