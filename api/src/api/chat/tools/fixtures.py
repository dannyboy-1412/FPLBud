from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.db.repos import current_season_id
from fplcore.db.stats_repo import fixtures_for, next_gw_id


class FixtureArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    view: Literal["team", "ticker"] = "team"
    team_id: int | None = None
    gameweeks: list[int] | None = Field(default=None, max_length=6)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = FixtureArgs.model_validate(args.model_dump())
    try:
        season = ctx.season_id or current_season_id(conn)
        start = next_gw_id(conn, season)
    except RuntimeError:
        return failure("NO_DATA", "No season is loaded.")
    if parsed.view == "ticker":
        window = parsed.gameweeks or [start + offset for offset in range(5)]
        teams = _teams(conn, season)
        rows = fixtures_for(conn, season, window)
        return ok(
            build_ticker(teams, rows, window),
            as_of=lookup_as_of(conn),
            data_version=ctx.data_version,
            notes=["Ease is the average of (5-FDR)/4. A blank week counts as 0."],
        )
    gws = parsed.gameweeks or [start, start + 1, start + 2]
    rows = fixtures_for(conn, season, gws, parsed.team_id)
    return ok(
        _team_view(rows, gws, parsed.team_id),
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
        notes=["Unscheduled fixtures have no gameweek yet."],
    )


def build_ticker(
    teams: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    gameweeks: list[int],
) -> dict[str, Any]:
    """All clubs sorted by average ease, plus league-wide blanks and doubles."""
    by_team: dict[int, dict[int, list[dict[str, Any]]]] = {}
    for row in fixtures:
        event = row.get("event")
        if event is None:
            continue
        gw = int(event)
        if gw not in gameweeks:
            continue
        by_team.setdefault(int(row["team_h"]), {}).setdefault(gw, []).append(
            {"opponent": row.get("away_short"), "fdr": int(row["team_h_difficulty"]), "home": True}
        )
        by_team.setdefault(int(row["team_a"]), {}).setdefault(gw, []).append(
            {"opponent": row.get("home_short"), "fdr": int(row["team_a_difficulty"]), "home": False}
        )
    clubs = []
    blanks: dict[str, list[str]] = {}
    doubles: dict[str, list[str]] = {}
    for team in teams:
        team_id = int(team["id"])
        short = str(team["short_name"])
        weeks = []
        ease_sum = 0.0
        ease_count = 0
        for gw in gameweeks:
            matches = by_team.get(team_id, {}).get(gw, [])
            weeks.append({"gw": gw, "matches": matches})
            if not matches:
                ease_sum += 0.0
                ease_count += 1
                blanks.setdefault(str(gw), []).append(short)
            else:
                for match in matches:
                    ease_sum += (5 - int(match["fdr"])) / 4
                    ease_count += 1
                if len(matches) > 1:
                    doubles.setdefault(str(gw), []).append(short)
        ease = round(ease_sum / ease_count, 3) if ease_count else 0.0
        clubs.append({"team_id": team_id, "team": short, "ease": ease, "gameweeks": weeks})
    clubs.sort(key=lambda club: (-float(club["ease"]), str(club["team"])))
    return {"clubs": clubs, "blanks": blanks, "doubles": doubles}


def _team_view(rows: list[dict[str, Any]], gws: list[int], team_id: int | None) -> dict[str, Any]:
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
    blanks: list[int] = []
    doubles: list[int] = []
    if team_id is not None:
        counts: dict[int, int] = defaultdict(int)
        for event in by_team.get(team_id, []):
            if event is not None:
                counts[int(event)] += 1
        for gw in gws:
            played = counts.get(gw, 0)
            if played == 0:
                blanks.append(gw)
            elif played > 1:
                doubles.append(gw)
    return {"fixtures": fixtures[:40], "blanks": blanks, "doubles": doubles}


def _teams(conn: Any, season: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "select id, short_name from teams where season_id = %s order by id",
        [season],
    ).fetchall()
    return [dict(row) for row in rows]


get_fixtures = BoundTool(
    name="get_fixtures",
    description="Fixtures for one club (view team) or a league ticker of the easiest runs, blanks and doubles (view ticker).",
    args_model=FixtureArgs,
    handler=_run,
)
