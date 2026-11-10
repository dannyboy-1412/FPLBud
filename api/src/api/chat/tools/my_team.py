from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from api.chat.context import build_context
from api.chat.tools.common import NoArgs, ok
from api.chat.tools.reading import lookup_as_of
from api.services import ranked_players
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS


def _player(row: Any, *, captain_id: int | None, vice_id: int | None, by_gw: list[float]) -> dict[str, Any]:
    return {
        "id": row.player_id,
        "name": row.name,
        "team": row.team,
        "position": row.position,
        "price_m": row.price_m,
        "proj": row.proj,
        "proj_by_gw": by_gw,
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
    ranked = {
        int(row["id"]): row
        for row in ranked_players(conn, weights=ctx.weights or DEFAULT_WEIGHTS, horizon=3)
    }
    return ok(
        {
            "team_name": view.team_name,
            "bank_m": view.bank_m,
            "free_transfers": view.free_transfers,
            "free_transfers_estimated": True,
            "chips_available": view.chips_available,
            "chips_used": view.chips_used,
            "starters": [
                _player(row, captain_id=view.captain_id, vice_id=view.vice_id, by_gw=_series(ranked, row.player_id))
                for row in view.starters
            ],
            "bench": [
                _player(row, captain_id=view.captain_id, vice_id=view.vice_id, by_gw=_series(ranked, row.player_id))
                for row in view.bench
            ],
            "flags": view.flags[:6],
        },
        as_of=lookup_as_of(conn) or view.data_as_of,
        data_version=view.data_version,
        notes=[
            "Free transfers are an estimate.",
            "This is the latest published squad. Transfers for a deadline that has not passed are hidden.",
            "proj_by_gw is the next three gameweeks.",
        ],
    )


def _series(ranked: dict[int, dict[str, Any]], player_id: int) -> list[float]:
    by_gw = list(ranked.get(player_id, {}).get("by_gw") or [])
    points = [float(item["proj"]) for item in by_gw[:3]]
    while len(points) < 3:
        points.append(0.0)
    return points


get_my_team = BoundTool(
    name="get_my_team",
    description="The user's saved squad, bank, free transfers and flags. Does not include the FPL entry id.",
    args_model=NoArgs,
    handler=_run,
)
