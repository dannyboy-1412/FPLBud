from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from api.chat.context import build_context
from api.chat.tools.common import NoArgs, ok
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure


def _player(row: Any, *, captain_id: int | None, vice_id: int | None) -> dict[str, Any]:
    return {
        "id": row.player_id,
        "name": row.name,
        "team": row.team,
        "position": row.position,
        "price_m": row.price_m,
        "proj": row.proj,
        "status": row.status,
        "chance": row.chance,
        "captain": row.player_id == captain_id,
        "vice": row.player_id == vice_id,
    }


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    del args
    if not ctx.has_team:
        return failure(
            "NO_TEAM_SAVED",
            "Save a team on the dashboard first.",
            hint="Personalised tools need a saved squad.",
        )
    view = build_context(conn, ctx.user_id, now=ctx.now)
    if not view.has_team:
        return failure(
            "NO_TEAM_SAVED",
            "Save a team on the dashboard first.",
            hint="Personalised tools need a saved squad.",
        )
    return ok(
        {
            "team_name": view.team_name,
            "bank_m": view.bank_m,
            "free_transfers": view.free_transfers,
            "free_transfers_estimated": True,
            "chips_available": view.chips_available,
            "chips_used": view.chips_used,
            "starters": [_player(row, captain_id=view.captain_id, vice_id=view.vice_id) for row in view.starters],
            "bench": [_player(row, captain_id=view.captain_id, vice_id=view.vice_id) for row in view.bench],
            "flags": view.flags[:6],
        },
        as_of=view.data_as_of,
        data_version=view.data_version,
        notes=["Free transfers are an estimate from the last import."],
    )


get_my_team = BoundTool(
    name="get_my_team",
    description="The user's saved squad, bank, free transfers and flags. Does not include the FPL entry id.",
    args_model=NoArgs,
    handler=_run,
)
