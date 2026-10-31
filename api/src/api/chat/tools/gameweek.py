from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from api.chat.context import build_context
from api.chat.tools.common import NoArgs, ok
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    del args
    view = build_context(conn, ctx.user_id, now=ctx.now)
    hours = None if view.hours_to_deadline is None else round(view.hours_to_deadline, 1)
    return ok(
        {
            "season_id": view.season_id or None,
            "decision_gw": view.decision_gw,
            "decision_name": view.decision_name or None,
            "deadline_utc": view.deadline_utc,
            "hours_to_deadline": hours,
            "deadline_passed": view.deadline_passed,
            "phase": view.phase,
            "started_gw": view.started_gw,
            "started_finished": view.started_finished,
            "stale": view.stale,
            "has_team": view.has_team,
        },
        as_of=view.data_as_of,
        data_version=view.data_version,
        notes=["Data is stale. Say so."] if view.stale else [],
    )


get_gameweek_context = BoundTool(
    name="get_gameweek_context",
    description="Current decision gameweek, deadline, and whether the data is stale. Call this before advice about the week.",
    args_model=NoArgs,
    handler=_run,
)
