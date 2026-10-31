from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.chat.tools.common import ok
from api.chat.tools.shape import take
from api.services import insights_payload, squad_stats_payload
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db import chat_repo


class InsightArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    view: str | None = Field(default=None)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = InsightArgs.model_validate(args.model_dump())
    weights = ctx.weights or DEFAULT_WEIGHTS
    view = parsed.view or "in_form"
    if view == "squad":
        if not ctx.has_team:
            return failure("NO_TEAM_SAVED", "Save a team on the dashboard first.")
        snapshot = chat_repo.latest_snapshot(conn, ctx.user_id)
        if snapshot is None:
            return failure("NO_TEAM_SAVED", "Save a team on the dashboard first.")
        payload = squad_stats_payload(conn, snapshot, weights)
        return ok(
            {
                "captaincy": _head(payload.get("captaincy")),
                "template_threats": take(list(payload.get("template_threats") or [])),
                "differentials": take(list(payload.get("differentials") or [])),
                "ownership": payload.get("ownership"),
            },
            as_of=None,
            data_version=ctx.data_version,
        )
    if view == "availability":
        snapshot = chat_repo.latest_snapshot(conn, ctx.user_id) if ctx.has_team else None
        flags = list((snapshot or {}).get("flags") or [])[:6]
        return ok({"flags": flags}, as_of=None, data_version=ctx.data_version)
    payload = insights_payload(conn, weights=weights)
    key = {
        "in_form": "in_form",
        "differentials": "differentials",
        "defensive": "defensive",
        "bonus": "bonus",
        "set_pieces": "set_pieces",
    }.get(view, "in_form")
    return ok(
        {key: take(list(payload.get(key) or []))},
        as_of=None,
        data_version=ctx.data_version,
    )


def _head(value: Any) -> Any:
    if isinstance(value, list):
        return value[:3]
    return value


get_insights = BoundTool(
    name="get_insights",
    description="Shortlists: in_form, differentials, defensive, bonus, set_pieces, squad, or availability flags.",
    args_model=InsightArgs,
    handler=_run,
)
