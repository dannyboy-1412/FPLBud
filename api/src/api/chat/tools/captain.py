"""Captain shortlist for the next gameweek. Every figure is already computed."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from api.chat.tools.common import NoArgs, ok
from api.chat.tools.reading import lookup_as_of, no_team, user_snapshot
from api.services import ranked_players, squad_stats_payload
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import latest_succeeded_run


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    del args
    snapshot = user_snapshot(ctx, conn)
    if snapshot is None:
        return no_team()
    weights = ctx.weights or DEFAULT_WEIGHTS
    payload = squad_stats_payload(conn, {"picks": snapshot.picks}, weights)
    ranked = {int(row["id"]): row for row in ranked_players(conn, weights=weights, horizon=1)}
    board = list((payload.get("captaincy") or {}).get("board") or [])
    options = [_option(row, ranked.get(int(row["id"]), {})) for row in board[:5]]
    plan = _plan_captain(conn, ctx)
    crowd = (payload.get("captaincy") or {}).get("crowd")
    return ok(
        {
            "options": options,
            "plan_captain_id": plan.get("captain_id"),
            "plan_vice_id": plan.get("vice_id"),
            "crowd": _crowd(crowd),
            "captain_margin": (payload.get("captaincy") or {}).get("gap"),
            "triple_captain": plan.get("triple_captain"),
        },
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
        notes=["Triple captain advice is a heuristic from the saved plan."],
    )


def _option(row: dict[str, Any], ranked: dict[str, Any]) -> dict[str, Any]:
    scores = ranked.get("scores") if isinstance(ranked.get("scores"), dict) else {}
    fixtures = []
    for item in list(row.get("fixtures") or []):
        if not isinstance(item, dict):
            continue
        fixtures.append(
            {
                "opponent": item.get("opponent"),
                "fdr": item.get("fdr"),
                "home": bool(item.get("is_home")),
            }
        )
    return {
        "id": int(row["id"]),
        "name": row.get("web_name"),
        "proj": row.get("proj"),
        "fixtures": fixtures,
        "minutes": scores.get("minutes"),
        "chance": row.get("chance_of_playing_next_round"),
        "own": row.get("selected_by_percent"),
    }


def _crowd(crowd: object) -> dict[str, Any] | None:
    if not isinstance(crowd, dict) or crowd.get("id") is None:
        return None
    return {"id": int(crowd["id"]), "name": crowd.get("web_name"), "team": crowd.get("team_short")}


def _plan_captain(conn: Any, ctx: ToolContext) -> dict[str, Any]:
    run = latest_succeeded_run(conn, ctx.user_id)
    if run is None:
        return {}
    row = conn.execute(
        """
        select plan, chip_advice
          from agent_suggestions
         where run_id = %s and horizon = 1
        """,
        [run["id"]],
    ).fetchone()
    if row is None:
        return {}
    plan = row["plan"] if isinstance(row["plan"], dict) else {}
    captain = plan.get("captain") if isinstance(plan.get("captain"), dict) else {}
    vice = plan.get("vice") if isinstance(plan.get("vice"), dict) else {}
    chips = row["chip_advice"] if isinstance(row["chip_advice"], list) else []
    triple = next((chip for chip in chips if isinstance(chip, dict) and chip.get("chip") == "3xc"), None)
    return {
        "captain_id": captain.get("id"),
        "vice_id": vice.get("id"),
        "triple_captain": _triple(triple),
    }


def _triple(chip: dict[str, Any] | None) -> dict[str, Any] | None:
    if chip is None:
        return None
    recommend = str(chip.get("recommend") or "")
    best = chip.get("best_gw")
    if best is None and recommend.startswith("consider_gw_"):
        suffix = recommend.removeprefix("consider_gw_")
        best = int(suffix) if suffix.isdigit() else None
    return {
        "recommend": recommend,
        "expected_gain": chip.get("expected_gain"),
        "best_gw": best,
        "expires_soon": bool(chip.get("expires_soon")),
    }


get_captain_options = BoundTool(
    name="get_captain_options",
    description="Top captain picks for the next gameweek, the saved plan's captain, the crowd pick, and triple-captain advice when that chip is available.",
    args_model=NoArgs,
    handler=_run,
)
