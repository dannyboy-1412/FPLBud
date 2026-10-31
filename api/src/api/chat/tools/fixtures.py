from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.chat.tools.common import ok
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.db.repos import current_season_id
from fplcore.db.stats_repo import fixtures_for, next_gw_id


class FixtureArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: int | None = None
    gameweeks: list[int] | None = Field(default=None, max_length=5)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = FixtureArgs.model_validate(args.model_dump())
    try:
        season = ctx.season_id or current_season_id(conn)
    except RuntimeError:
        return failure("NO_DATA", "No season is loaded.")
    start = next_gw_id(conn, season)
    gws = parsed.gameweeks or [start, start + 1, start + 2]
    rows = fixtures_for(conn, season, gws, parsed.team_id)
    by_team: dict[int, list[int | None]] = defaultdict(list)
    fixtures = []
    for row in rows:
        event = row["event"]
        fixtures.append(
            {
                "id": int(row["id"]),
                "gw": int(event) if event is not None else None,
                "home": row["home_short"],
                "away": row["away_short"],
                "home_fdr": int(row["team_h_difficulty"]),
                "away_fdr": int(row["team_a_difficulty"]),
                "unscheduled": event is None,
            }
        )
        by_team[int(row["team_h"])].append(event)
        by_team[int(row["team_a"])].append(event)
    blanks = []
    doubles = []
    scheduled_gws = [gw for gw in gws]
    if parsed.team_id is not None:
        counts: dict[int, int] = defaultdict(int)
        for event in by_team.get(parsed.team_id, []):
            if event is not None:
                counts[int(event)] += 1
        for gw in scheduled_gws:
            played = counts.get(gw, 0)
            if played == 0:
                blanks.append(gw)
            elif played > 1:
                doubles.append(gw)
    return ok(
        {"fixtures": fixtures[:40], "blanks": blanks, "doubles": doubles},
        as_of=None,
        data_version=ctx.data_version,
        notes=["Unscheduled fixtures have no gameweek yet."],
    )


get_fixtures = BoundTool(
    name="get_fixtures",
    description="Fixtures for the next gameweeks, including blanks, doubles and unscheduled matches.",
    args_model=FixtureArgs,
    handler=_run,
)
