from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.chat.context import plan_squad_differs, pounds
from api.chat.tools.common import ok
from api.chat.tools.reading import lookup_as_of, no_team, user_snapshot
from api.services import build_horizon_plan, load_opt_players
from fplcore.chat.moves import MoveInput, quote_transfers
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db import chat_repo
from fplcore.db.repos import latest_succeeded_run
from fplcore.optimise import PlayerOpt
from fplcore.rules import IncomingPlayer, SquadSlot


class PlanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OptimiseArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    horizon: Literal[1, 3, 5]
    lock_ids: list[int] | None = None
    exclude_ids: list[int] | None = None


class Move(BaseModel):
    model_config = ConfigDict(extra="forbid")
    out_player_id: int
    in_player_id: int


class EvaluateTransfersArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    moves: list[Move] = Field(min_length=1, max_length=3)
    horizon: Literal[1, 3, 5]


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
        select horizon, plan, hits, gain_vs_roll, explanation, alternatives, chip_advice, reason_codes
          from agent_suggestions
         where run_id = %s
         order by horizon
        """,
        [run["id"]],
    ).fetchall()
    stale = ctx.data_version is not None and run.get("data_version") not in {None, ctx.data_version}
    plans = [shape_saved_plan(dict(row)) for row in rows]
    notes = ["Saved plan is older than the current data."] if stale else []
    notes.append("Chip timing is a heuristic.")
    return ok(
        {"plans": plans, "stale": stale, "chips_are_heuristic": True},
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
        notes=notes,
    )


def _optimise(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = OptimiseArgs.model_validate(args.model_dump())
    if not ctx.has_team:
        return failure("NO_TEAM_SAVED", "Save a team on the dashboard first.")
    if not chat_repo.consume_optimiser(conn, ctx.user_id, ctx.optimiser_hourly_cap):
        return failure(
            "RATE_LIMITED",
            "The optimiser has been used enough this hour.",
            hint="Use get_plan_suggestions.",
        )
    snapshot = user_snapshot(ctx, conn)
    if snapshot is None:
        return failure("NO_TEAM_SAVED", "Save a team on the dashboard first.")
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
        as_of=lookup_as_of(conn),
        data_version=ctx.data_version,
        notes=["Chip timing is a heuristic, not part of this solve."],
    )


def _evaluate(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = EvaluateTransfersArgs.model_validate(args.model_dump())
    snapshot = user_snapshot(ctx, conn)
    if snapshot is None:
        return no_team()
    loaded = load_opt_players(conn, snapshot, ctx.weights or DEFAULT_WEIGHTS, parsed.horizon)
    opts = {player.id: player for player in loaded}
    inputs: list[MoveInput] = []
    for move in parsed.moves:
        incoming = opts.get(move.in_player_id)
        if incoming is None:
            return failure("NOT_FOUND", "That player is not in the list.", hint="Use search_players.")
        outgoing = opts.get(move.out_player_id)
        inputs.append(
            MoveInput(
                out_player_id=move.out_player_id,
                incoming=_incoming(incoming),
                out_name=outgoing.web_name if outgoing else str(move.out_player_id),
                in_name=incoming.web_name,
                out_proj=_horizon_proj(outgoing),
                in_proj=_horizon_proj(incoming),
            )
        )
    quote = quote_transfers(
        _slots(opts),
        inputs,
        bank=int(snapshot.bank),
        free_transfers=int(snapshot.free_transfers),
        horizon=parsed.horizon,
    )
    payload = quote.as_dict()
    payload["bank_after_m"] = pounds(quote.bank_after)
    payload.pop("bank_after", None)
    return ok(payload, as_of=lookup_as_of(conn), data_version=ctx.data_version)


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


def shape_saved_plan(row: dict[str, Any]) -> dict[str, Any]:
    """The stored plan fields the model needs, including chip advice and the roll alternative."""
    body = _object(row.get("plan"))
    return {
        "horizon": int(row["horizon"]),
        "headline": body.get("headline"),
        "hits": int(row["hits"] or 0),
        "gain_vs_roll": float(row["gain_vs_roll"]) if row.get("gain_vs_roll") is not None else None,
        "explanation": str(row.get("explanation") or "")[:400],
        "transfers": _plan_transfers(body.get("transfers")),
        "captain_id": _id_of(body.get("captain")),
        "vice_id": _id_of(body.get("vice")),
        "xi": _ids(body.get("xi")),
        "bench": _ids(body.get("bench")),
        "projected_points_by_gw": body.get("projected_points_by_gw") or {},
        "bank_after_m": pounds(body.get("bank_after")),
        "alternatives": [_alternative(item) for item in _list(row.get("alternatives"))[:2]],
        "chip_advice": [_chip(item) for item in _list(row.get("chip_advice"))],
        "reason_codes": list(row.get("reason_codes") or body.get("reason_codes") or []),
    }


def _incoming(player: PlayerOpt) -> IncomingPlayer:
    return IncomingPlayer(
        player_id=player.id,
        position_id=player.position_id,
        team_id=player.team_id,
        now_cost=player.cost,
        can_transact=player.can_in,
    )


def _slots(opts: dict[int, PlayerOpt]) -> list[SquadSlot]:
    return [
        SquadSlot(player.id, player.position_id, player.team_id, player.sell)
        for player in opts.values()
        if player.in_squad
    ]


def _horizon_proj(player: PlayerOpt | None) -> float:
    if player is None:
        return 0.0
    return round(sum(player.proj), 2)


def _plan_transfers(raw: object) -> list[dict[str, Any]]:
    transfers: list[dict[str, Any]] = []
    for item in _list(raw)[:4]:
        deltas = item.get("metric_deltas") if isinstance(item.get("metric_deltas"), dict) else {}
        ranked = sorted(deltas.items(), key=lambda pair: abs(float(pair[1] or 0)), reverse=True)[:2]
        transfers.append(
            {
                "out_id": item.get("out"),
                "in_id": item.get("in"),
                "out_name": item.get("out_name"),
                "in_name": item.get("in_name"),
                "cost_delta_m": pounds(item.get("cost_delta")),
                "metric_deltas": {str(key): round(float(value), 3) for key, value in ranked},
            }
        )
    return transfers


def _alternative(item: dict[str, Any]) -> dict[str, Any]:
    points = item.get("projected_points_by_gw") if isinstance(item.get("projected_points_by_gw"), dict) else {}
    total = round(sum(float(value) for value in points.values()), 2) if points else None
    return {
        "hits": item.get("hits"),
        "transfer_count": len(item.get("transfers") or []),
        "projected_points_by_gw": points,
        "projected_total": total,
        "gain_vs_roll": item.get("gain_vs_roll"),
    }


def _chip(item: dict[str, Any]) -> dict[str, Any]:
    recommend = str(item.get("recommend") or "")
    best = item.get("best_gw")
    if best is None and recommend.startswith("consider_gw_"):
        suffix = recommend.removeprefix("consider_gw_")
        best = int(suffix) if suffix.isdigit() else None
    return {
        "chip": item.get("chip"),
        "recommend": recommend,
        "best_gw": best,
        "expected_gain": item.get("expected_gain"),
        "expires_soon": bool(item.get("expires_soon")),
    }


def _id_of(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and isinstance(value.get("id"), int):
        return int(value["id"])
    return None


def _ids(raw: object) -> list[int]:
    found: list[int] = []
    for item in _list(raw):
        player_id = _id_of(item)
        if player_id is None and isinstance(item, int):
            player_id = item
        if player_id is not None:
            found.append(player_id)
    return found


def _list(raw: object) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _object(raw: object) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


get_plan_suggestions = BoundTool(
    name="get_plan_suggestions",
    description="The saved 1, 3 and 5 gameweek plans, with transfers, the XI, alternatives and chip advice. Chip lines are a heuristic.",
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

evaluate_transfers = BoundTool(
    name="evaluate_transfers",
    description="Legality, projected delta, hit cost and net for one to three moves over 1, 3 or 5 gameweeks. Quote verdict and net_after_hits.",
    args_model=EvaluateTransfersArgs,
    handler=_evaluate,
)
