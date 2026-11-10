from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of
from api.chat.tools.shape import take
from api.services import insights_payload, squad_stats_payload
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db import chat_repo
from fplcore.db.repos import current_season_id

InsightView = Literal[
    "in_form",
    "differentials",
    "defensive",
    "bonus",
    "set_pieces",
    "squad",
    "availability",
    "injuries",
]


class InsightArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    view: InsightView


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = InsightArgs.model_validate(args.model_dump())
    weights = ctx.weights or DEFAULT_WEIGHTS
    view = parsed.view
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
            as_of=lookup_as_of(conn),
            data_version=ctx.data_version,
        )
    if view == "availability":
        snapshot = chat_repo.latest_snapshot(conn, ctx.user_id) if ctx.has_team else None
        flags = list((snapshot or {}).get("flags") or [])[:6]
        return ok({"flags": flags}, as_of=lookup_as_of(conn), data_version=ctx.data_version)
    if view == "injuries":
        return ok(
            {"players": _injuries(conn, ctx.season_id)},
            as_of=lookup_as_of(conn),
            data_version=ctx.data_version,
            notes=["This is the league list, not only the user's squad."],
        )
    payload = insights_payload(conn, weights=weights)
    return ok(
        {view: take(list(payload.get(view) or []))},
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
    )


def _head(value: Any) -> Any:
    if isinstance(value, list):
        return value[:3]
    return value


def _injuries(conn: Any, season_id: str | None) -> list[dict[str, Any]]:
    try:
        season = season_id or current_season_id(conn)
    except RuntimeError:
        return []
    rows = conn.execute(
        """
        select p.id, p.web_name, p.status, p.chance_of_playing_next_round, p.news,
               t.short_name as team_short
          from players p
          join teams t on t.season_id = p.season_id and t.id = p.team_id
         where p.season_id = %s and p.status in ('d', 'i', 's', 'u')
         order by p.status, p.web_name
         limit 8
        """,
        [season],
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "name": row["web_name"],
            "team": row["team_short"],
            "status": row["status"],
            "chance": row["chance_of_playing_next_round"],
            "news": row["news"] or "",
        }
        for row in rows
    ]


get_insights = BoundTool(
    name="get_insights",
    description="Shortlists. view is in_form, differentials, defensive, bonus, set_pieces, squad, availability or injuries.",
    args_model=InsightArgs,
    handler=_run,
)
