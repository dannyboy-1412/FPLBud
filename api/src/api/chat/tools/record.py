"""Season record for one player, already split by fixture difficulty and venue."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import POSITION_SHORT
from fplcore.db.repos import current_season_id
from fplcore.db.stats_repo import player_match_rows
from fplcore.stats.player_record import build_player_record

_MATCH_CAP = 20
_FDR_NOTE = (
    "Easy is FDR 1-2, medium 3, hard 4-5, from the player's side. "
    "FDR is FPL's current rating for that fixture."
)


class PlayerRecordArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: int
    last_n_gws: int | None = Field(default=None, ge=1, le=38)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = PlayerRecordArgs.model_validate(args.model_dump())
    try:
        season = ctx.season_id or current_season_id(conn)
    except RuntimeError:
        return failure("NO_DATA", "No season is loaded.")
    player = _player(conn, season, parsed.player_id)
    if player is None:
        return failure("NOT_FOUND", "No player with that id.", hint="Use resolve_players.")
    rows = player_match_rows(conn, season, parsed.player_id, _min_round(conn, season, parsed))
    record = build_player_record(rows)
    shown = list(record["matches"])
    notes = [_FDR_NOTE]
    if len(shown) > _MATCH_CAP:
        record["matches"] = shown[:_MATCH_CAP]
        notes.append("Match list shows the latest 20. Totals cover the whole window.")
    if not rows:
        notes.append(_empty_note(player))
    rounds = [int(row["round"]) for row in rows]
    return ok(
        {
            "id": int(player["id"]),
            "name": player["web_name"],
            "team": player.get("team_short"),
            "position": POSITION_SHORT.get(int(player["position_id"]), "?"),
            "from_gw": min(rounds) if rounds else None,
            "to_gw": max(rounds) if rounds else None,
            **record,
        },
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
        notes=notes,
    )


def _min_round(conn: Any, season: str, parsed: PlayerRecordArgs) -> int | None:
    if parsed.last_n_gws is None:
        return None
    row = conn.execute(
        """
        select max(round) as latest
          from player_match_points
         where season_id = %s and player_id = %s
        """,
        [season, parsed.player_id],
    ).fetchone()
    latest = row["latest"] if row else None
    if latest is None:
        return None
    return max(1, int(latest) - parsed.last_n_gws + 1)


def _player(conn: Any, season: str, player_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        select p.id, p.web_name, p.position_id, p.minutes, t.short_name as team_short
          from players p
          join teams t on t.season_id = p.season_id and t.id = p.team_id
         where p.season_id = %s and p.id = %s
        """,
        [season, player_id],
    ).fetchone()
    return dict(row) if row else None


def _empty_note(player: dict[str, Any]) -> str:
    if int(player.get("minutes") or 0) <= 0:
        return "This player has not played this season."
    return "History for this player is still loading."


get_player_record = BoundTool(
    name="get_player_record",
    description=(
        "One player's season points already split by fixture difficulty "
        "(easy FDR 1-2, medium 3, hard 4-5) and by home or away."
    ),
    args_model=PlayerRecordArgs,
    handler=_run,
)
