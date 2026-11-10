"""Name lookup for the cases the pre-pass missed."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.chat.context import pounds
from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of
from fplcore.chat.names import NameRecord, match_query
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import POSITION_SHORT
from fplcore.db.repos import current_season_id


class ResolveArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    names: list[str] = Field(min_length=1, max_length=5)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = ResolveArgs.model_validate(args.model_dump())
    try:
        season = ctx.season_id or current_season_id(conn)
    except RuntimeError:
        return failure("NO_DATA", "No season is loaded.")
    players = _records(conn, season)
    matches: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    missed: list[str] = []
    for name in parsed.names:
        found = match_query(name, players)
        if not found:
            missed.append(name.strip())
            continue
        if len(found) > 1:
            ambiguous.append(
                {
                    "query": name.strip(),
                    "candidates": [_brief(player) for player in found[:4]],
                }
            )
            continue
        matches.append({"query": name.strip(), **_brief(found[0])})
    if ambiguous:
        return failure(
            "PLAYER_AMBIGUOUS",
            "Some names match more than one player.",
            hint="Ask which club.",
            candidates=ambiguous,
        )
    if not matches:
        return failure("NO_MATCH", "No player matched those names.", hint="Try a shorter name.")
    return ok(
        {"matches": matches, "misses": missed},
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
    )


def _records(conn: Any, season_id: str) -> list[NameRecord]:
    rows = conn.execute(
        """
        select p.id, p.web_name, p.first_name, p.second_name, p.now_cost, p.position_id,
               t.short_name as team_short
          from players p
          join teams t on t.season_id = p.season_id and t.id = p.team_id
         where p.season_id = %s and p.removed = false
        """,
        [season_id],
    ).fetchall()
    return [
        NameRecord(
            player_id=int(row["id"]),
            web_name=str(row["web_name"] or ""),
            first_name=str(row["first_name"] or ""),
            second_name=str(row["second_name"] or ""),
            team=str(row["team_short"] or ""),
            position=POSITION_SHORT.get(int(row["position_id"]), "?"),
            price_m=pounds(row["now_cost"]) or 0.0,
        )
        for row in rows
    ]


def _brief(player: NameRecord) -> dict[str, Any]:
    return {
        "id": player.player_id,
        "name": player.web_name,
        "team": player.team,
        "position": player.position,
        "price_m": player.price_m,
    }


resolve_players = BoundTool(
    name="resolve_players",
    description="Resolve up to five player names to ids. Ambiguous names return PLAYER_AMBIGUOUS with the candidates.",
    args_model=ResolveArgs,
    handler=_run,
)
