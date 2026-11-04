from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.chat.context import plan_squad_differs, pounds
from api.chat.tools.common import ok
from api.services import build_horizon_plan
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db import chat_repo
from fplcore.db.repos import latest_succeeded_run
from fplcore.rules import IncomingPlayer, SquadSlot, check_transfer
from fplcore.team_import import apply_overrides, snapshot_from_row


class PlanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OptimiseArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    horizon: int = Field(ge=1, le=5)
    lock_ids: list[int] | None = None
    exclude_ids: list[int] | None = None


class EvaluateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    out_player_id: int
    in_player_id: int


def _suggestions(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    del args
    run = latest_succeeded_run(conn, ctx.user_id)
    if run is None:
        return failure("NO_PLAN", "There is no saved plan yet.", hint="Open the dashboard and let the agent finish.")
    if plan_squad_differs(ctx.snapshot_id, run.get("snapshot_id")):
        return ok(
            {"plans": [], "stale": True, "chips_are_heuristic": True},
            as_of=None,
            data_version=ctx.data_version,
            notes=["The saved plan is for an older squad. A new one is being prepared."],
        )
    rows = conn.execute(
        """
        select horizon, plan, hits, gain_vs_roll, explanation
          from agent_suggestions
         where run_id = %s
         order by horizon
        """,
        [run["id"]],
    ).fetchall()
    stale = ctx.data_version is not None and run.get("data_version") not in {None, ctx.data_version}
    plans = []
    for row in rows:
        body = row["plan"] if isinstance(row["plan"], dict) else {}
        plans.append(
            {
                "horizon": int(row["horizon"]),
                "headline": body.get("headline"),
                "hits": int(row["hits"] or 0),
                "gain_vs_roll": float(row["gain_vs_roll"]) if row["gain_vs_roll"] is not None else None,
                "explanation": str(row["explanation"] or "")[:400],
            }
        )
    notes = ["Saved plan is older than the current data."] if stale else []
    return ok(
        {"plans": plans, "stale": stale, "chips_are_heuristic": True},
        as_of=None,
        data_version=ctx.data_version,
        notes=notes,
    )


def _optimise(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = OptimiseArgs.model_validate(args.model_dump())
    if parsed.horizon not in {1, 3, 5}:
        return failure("INVALID_ARGUMENT", "Horizon must be 1, 3 or 5.")
    if not ctx.has_team:
        return failure("NO_TEAM_SAVED", "Save a team on the dashboard first.")
    if not chat_repo.consume_optimiser(conn, ctx.user_id, ctx.optimiser_hourly_cap):
        return failure(
            "RATE_LIMITED",
            "The optimiser has been used enough this hour.",
            hint="Use get_plan_suggestions.",
        )
    stored = chat_repo.latest_snapshot(conn, ctx.user_id)
    if stored is None:
        return failure("NO_TEAM_SAVED", "Save a team on the dashboard first.")
    snapshot = apply_overrides(snapshot_from_row(stored), stored.get("overrides"))
    plan = build_horizon_plan(
        conn,
        snapshot,
        weights=ctx.weights or DEFAULT_WEIGHTS,
        horizon=parsed.horizon,
        max_hits=ctx.max_hits,
        lock_ids=parsed.lock_ids,
        exclude_ids=parsed.exclude_ids,
    )
    if plan is None:
        return failure("NO_SOLUTION", "The optimiser could not build a plan.", hint="Use get_plan_suggestions.")
    raw_captain = plan.get("captain")
    captain = raw_captain if isinstance(raw_captain, dict) else {}
    return ok(
        {
            "headline": plan.get("headline"),
            "hits": plan.get("hits"),
            "captain_id": captain.get("id"),
            "transfers": _moves(plan.get("transfers")),
            "explanation": str(plan.get("explanation") or "")[:400],
            "chips_are_heuristic": True,
        },
        as_of=None,
        data_version=ctx.data_version,
        notes=["Chip timing is a heuristic, not part of this solve."],
    )


def _evaluate(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = EvaluateArgs.model_validate(args.model_dump())
    if not ctx.has_team or not ctx.season_id:
        return failure("NO_TEAM_SAVED", "Save a team on the dashboard first.")
    stored = chat_repo.latest_snapshot(conn, ctx.user_id)
    if stored is None:
        return failure("NO_TEAM_SAVED", "Save a team on the dashboard first.")
    snapshot = apply_overrides(snapshot_from_row(stored), stored.get("overrides"))
    incoming = _incoming(conn, ctx.season_id, parsed.in_player_id)
    if incoming is None:
        return failure("NOT_FOUND", "That player is not in the list.", hint="Use search_players.")
    squad = _squad(conn, ctx.season_id, snapshot.picks, snapshot.selling_prices)
    verdict = check_transfer(squad, parsed.out_player_id, incoming, bank=snapshot.bank)
    return ok(
        {"legal": verdict.legal, "code": verdict.code, "message": verdict.message},
        as_of=None,
        data_version=ctx.data_version,
    )


def _moves(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    moves: list[dict[str, Any]] = []
    for item in raw[:4]:
        if not isinstance(item, dict):
            continue
        moves.append(
            {
                "out_id": item.get("out"),
                "in_id": item.get("in"),
                "out_name": item.get("out_name"),
                "in_name": item.get("in_name"),
                "cost_delta_m": pounds(item.get("cost_delta")),
            }
        )
    return moves


def _incoming(conn: Any, season: str, player_id: int) -> IncomingPlayer | None:
    row = conn.execute(
        """
        select id, position_id, team_id, now_cost, can_transact, status, removed
          from players
         where season_id = %s and id = %s
        """,
        [season, player_id],
    ).fetchone()
    if row is None:
        return None
    can = bool(row["can_transact"]) and not row["removed"] and row["status"] != "u"
    return IncomingPlayer(
        player_id=int(row["id"]),
        position_id=int(row["position_id"]),
        team_id=int(row["team_id"]),
        now_cost=int(row["now_cost"]),
        can_transact=can,
    )


def _squad(conn: Any, season: str, picks: list[dict[str, Any]], selling: dict[str, int]) -> list[SquadSlot]:
    ids = [int(pick["element"]) for pick in picks]
    if not ids:
        return []
    rows = conn.execute(
        "select id, position_id, team_id, now_cost from players where season_id = %s and id = any(%s)",
        [season, ids],
    ).fetchall()
    by_id = {int(row["id"]): row for row in rows}
    slots: list[SquadSlot] = []
    for player_id in ids:
        row = by_id.get(player_id)
        if row is None:
            continue
        slots.append(
            SquadSlot(
                player_id=player_id,
                position_id=int(row["position_id"]),
                team_id=int(row["team_id"]),
                sell=int(selling.get(str(player_id), row["now_cost"])),
            )
        )
    return slots


get_plan_suggestions = BoundTool(
    name="get_plan_suggestions",
    description="The saved 1, 3 and 5 gameweek plans. Says when the plan is older than the current data. Chip lines are a heuristic.",
    args_model=PlanArgs,
    handler=_suggestions,
)

run_transfer_optimiser = BoundTool(
    name="run_transfer_optimiser",
    description="Re-solve transfers for horizon 1, 3 or 5. Use only when the saved plan does not answer the question. Locks and excludes are player ids.",
    args_model=OptimiseArgs,
    handler=_optimise,
    timeout_s=15.0,
)

evaluate_transfer = BoundTool(
    name="evaluate_transfer",
    description="Check one transfer is legal: position, budget at selling price, three per club, already owned, and whether they can be bought.",
    args_model=EvaluateArgs,
    handler=_evaluate,
)
