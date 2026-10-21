from __future__ import annotations

import hashlib
import json
from typing import Any

from psycopg import Connection
from psycopg.types.json import Json

from fplcore.agent.chips import advise_chips
from fplcore.agent.queue import finish_run, update_progress
from fplcore.explain.factory import get_explainer
from fplcore.explain.llm import LLMExplainer
from fplcore.explain.protocol import HorizonResult
from fplcore.metrics.combine import availability, combined_score, projected_points
from fplcore.optimise import PlayerOpt, SolvedPlan, optimise_horizon
from fplcore.settings import Settings, get_settings


def _plan_hash(plan: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, default=str).encode()).hexdigest()


def _player_opts(
    conn: Connection,
    *,
    snapshot: dict[str, Any],
    weights: dict[str, float],
    next_gw: int,
    horizon: int,
    lock_ids: list[int] | None = None,
    exclude_ids: list[int] | None = None,
) -> list[PlayerOpt]:
    season_id = snapshot["season_id"]
    current = {int(p["element"]) for p in snapshot["picks"]}
    selling = {int(k): int(v) for k, v in (snapshot.get("selling_prices") or {}).items()}
    rows = list(
        conn.execute(
            """
            select p.id, p.web_name, p.team_id, p.position_id, p.now_cost, p.status,
                   p.chance_of_playing_next_round, p.can_transact, p.removed,
                   m.computed_for_gw, m.form_score, m.fixture_score, m.home_score, m.xgi_score,
                   m.value_score, m.minutes_score, m.trend_score, m.fixture_count, m.availability
              from players p
              join player_metrics m on m.season_id = p.season_id and m.player_id = p.id
             where p.season_id = %s and m.horizon = 1
               and m.computed_for_gw between %s and %s
            """,
            [season_id, next_gw, next_gw + max(horizon, 6) - 1],
        )
    )
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        rec = by_id.setdefault(
            int(row["id"]),
            {
                "id": int(row["id"]),
                "web_name": row["web_name"],
                "team_id": int(row["team_id"]),
                "position_id": int(row["position_id"]),
                "cost": int(row["now_cost"]),
                "sell": selling.get(int(row["id"]), int(row["now_cost"])),
                "in_squad": int(row["id"]) in current,
                "can_in": bool(row["can_transact"]) and not row["removed"] and row["status"] != "u",
                "proj": {},
                "scores_gw1": {},
            },
        )
        gw = int(row["computed_for_gw"])
        scores = {
            "form": float(row["form_score"] or 0),
            "fixture": float(row["fixture_score"] or 0),
            "home": float(row["home_score"] or 0),
            "xgi": float(row["xgi_score"] or 0),
            "value": float(row["value_score"] or 0),
            "minutes": float(row["minutes_score"] or 0),
            "trend": float(row["trend_score"] or 0),
        }
        k = gw - next_gw + 1
        score = combined_score(scores, weights)
        avail = availability(
            chance_of_playing_next_round=row["chance_of_playing_next_round"],
            status=row["status"],
            k=max(k, 1),
        )
        rec["proj"][gw] = projected_points(
            score=score, fixture_count=int(row["fixture_count"]), avail=avail
        )
        if gw == next_gw:
            rec["scores_gw1"] = scores
    locks = set(lock_ids or [])
    excludes = set(exclude_ids or [])
    out: list[PlayerOpt] = []
    for rec in by_id.values():
        proj = [float(rec["proj"].get(next_gw + i, 0.0)) for i in range(max(horizon, 6))]
        out.append(
            PlayerOpt(
                id=rec["id"],
                web_name=rec["web_name"],
                team_id=rec["team_id"],
                position_id=rec["position_id"],
                cost=rec["cost"],
                sell=rec["sell"],
                in_squad=rec["in_squad"],
                can_in=rec["can_in"] and rec["id"] not in excludes,
                locked=rec["id"] in locks,
                proj=proj,
                scores_gw1=rec["scores_gw1"],
            )
        )
    return out


def _player_brief(conn: Connection, player_id: int | None, season_id: str) -> dict[str, Any]:
    if player_id is None:
        return {}
    row = conn.execute(
        "select id, web_name, team_id, position_id, now_cost from players where season_id = %s and id = %s",
        [season_id, player_id],
    ).fetchone()
    return dict(row) if row else {"id": player_id}


def _horizon_result(
    conn: Connection,
    *,
    snapshot: dict[str, Any],
    players: list[PlayerOpt],
    solved: dict[str, Any],
    horizon: int,
    next_gw: int,
    chip_tips: list[dict[str, Any]],
) -> HorizonResult:
    best: SolvedPlan = solved["best"]
    roll: SolvedPlan | None = solved["roll"]
    fewer: SolvedPlan | None = solved["fewer"]
    by_id = {p.id: p for p in players}
    season_id = snapshot["season_id"]
    gain = round(best.objective - (roll.objective if roll else 0.0), 2)
    transfers = []
    for move in best.moves:
        transfers.append(
            {
                "out": move.out_id,
                "in": move.in_id,
                "out_name": move.out_name,
                "in_name": move.in_name,
                "cost_delta": move.cost_delta,
                "metric_deltas": move.metric_deltas,
            }
        )
    reason_codes: list[str] = []
    flagged_ids = {int(f["element"]) for f in snapshot.get("flags") or []}
    if any(m.out_id in flagged_ids for m in best.moves):
        reason_codes.append("FLAG_INJURED_OUT")
    if any((m.metric_deltas.get("fixture") or 0) > 0.1 for m in best.moves):
        reason_codes.append("FIXTURE_SWING")
    if any((m.metric_deltas.get("xgi") or 0) > 0.05 for m in best.moves):
        reason_codes.append("XGI_UPGRADE")
    if not best.moves:
        reason_codes.append("ROLL_PREFERRED")
    if best.hits == 0 and any(p.transfers_in > best.transfers_in for p in (solved["all"] or {}).values()):
        reason_codes.append("HIT_NOT_WORTH")
    reason_codes.append("CAPTAIN_MARGIN")

    def pack_player(pid: int | None) -> dict[str, Any]:
        brief = _player_brief(conn, pid, season_id)
        if pid in by_id:
            brief["proj"] = round(by_id[pid].proj[0], 2)
        return brief

    def pack_plan(plan: SolvedPlan) -> dict[str, Any]:
        return {
            "transfers": [
                {"out": m.out_id, "in" : m.in_id, "out_name": m.out_name, "in_name": m.in_name, "cost_delta": m.cost_delta}
                for m in plan.moves
            ],
            "hits": plan.hits,
            "gain_vs_roll": round(plan.objective - (roll.objective if roll else 0), 2),
            "projected_points_by_gw": plan.projected_points_by_gw,
        }

    result: HorizonResult = HorizonResult(
        {
            "horizon": horizon,
            "transfers": transfers,
            "hits": best.hits,
            "gain_vs_roll": gain,
            "roll_alternative": pack_plan(roll) if roll and roll is not best else None,
            "fewer_alternative": pack_plan(fewer) if fewer else None,
            "xi": [pack_player(pid) for pid in best.xi_ids],
            "bench": [pack_player(pid) for pid in best.bench_ids],
            "captain": pack_player(best.captain_id),
            "vice": pack_player(best.vice_id),
            "chips": chip_tips,
            "flags": snapshot.get("flags") or [],
            "reason_codes": reason_codes,
            "projected_points_by_gw": best.projected_points_by_gw,
            "bank_after": best.bank_after,
            "headline": (
                "Roll the transfer"
                if not transfers
                else ", ".join(f"Sell {t['out_name']}, buy {t['in_name']}" for t in transfers)
            ),
        }
    )
    return result


async def _explanations(
    results: dict[str, HorizonResult],
    settings: Settings,
    *,
    allow_llm: bool,
) -> tuple[dict[str, str], str]:
    explainer = get_explainer(settings)
    if allow_llm and isinstance(explainer, LLMExplainer):
        return await explainer.explain_run_async(results)
    texts = explainer.explain_run(results)
    return texts, getattr(explainer, "source", "template")


def _try_llm_cap(conn: Connection, cap: int) -> bool:
    row = conn.execute(
        """
        insert into llm_usage (day, calls) values (current_date, 1)
        on conflict (day) do update
          set calls = llm_usage.calls + 1
          where llm_usage.calls < %s
        returning calls
        """,
        [cap],
    ).fetchone()
    return row is not None


async def run_claimed(
    conn: Connection,
    run: dict[str, Any],
    *,
    settings: Settings | None = None,
    worker_id: str = "worker",
) -> None:
    cfg = settings or get_settings()
    run_id = int(run["id"])
    try:
        update_progress(conn, run_id, stage="context", progress=5)
        snapshot_row = conn.execute(
            "select * from team_snapshots where id = %s", [run["snapshot_id"]]
        ).fetchone()
        if snapshot_row is None:
            raise RuntimeError("snapshot missing")
        snapshot = {
            "id": snapshot_row["id"],
            "entry_id": snapshot_row["entry_id"],
            "event": snapshot_row["event"],
            "season_id": snapshot_row["season_id"],
            "picks": snapshot_row["picks"],
            "bank": snapshot_row["bank"],
            "team_value": snapshot_row["team_value"],
            "free_transfers": snapshot_row["free_transfers"],
            "selling_prices": snapshot_row["selling_prices"],
            "chips_available": snapshot_row["chips_available"],
            "chips_used": snapshot_row["chips_used"],
            "active_chip": snapshot_row["active_chip"],
            "flags": snapshot_row["flags"],
            "overrides": snapshot_row["overrides"],
        }
        gw = conn.execute(
            "select id from gameweeks where season_id = %s and is_next = true limit 1",
            [snapshot["season_id"]],
        ).fetchone()
        next_gw = int(gw["id"]) if gw else int(snapshot["event"]) + 1
        weights = dict(run["weights"] or {})
        unlimited = (snapshot.get("active_chip") or "") in {"wildcard", "freehit"}
        results: dict[str, HorizonResult] = {}
        stages = [("horizon_1", 1, 25), ("horizon_3", 3, 50), ("horizon_5", 5, 75)]
        players_h5 = _player_opts(conn, snapshot=snapshot, weights=weights, next_gw=next_gw, horizon=5)
        for stage, horizon, progress in stages:
            update_progress(conn, run_id, stage=stage, progress=progress)
            conn.commit()
            solved = optimise_horizon(
                players_h5,
                bank=int(snapshot["bank"]),
                free_transfers=int(snapshot["free_transfers"]),
                horizon=horizon,
                unlimited_transfers=unlimited,
            )
            update_progress(conn, run_id, stage="chips", progress=progress + 5)
            chips = advise_chips(
                snapshot=snapshot,
                best=solved["best"],
                players=players_h5,
                bank=int(snapshot["bank"]),
                next_gw=next_gw,
                horizon=horizon,
            )
            results[str(horizon)] = _horizon_result(
                conn,
                snapshot=snapshot,
                players=players_h5,
                solved=solved,
                horizon=horizon,
                next_gw=next_gw,
                chip_tips=chips,
            )

        update_progress(conn, run_id, stage="explain", progress=90)
        conn.commit()
        allow_llm = cfg.llm_enabled and run.get("trigger") in {"import", "user_rerun"}
        if allow_llm and not _try_llm_cap(conn, cfg.llm_daily_call_cap):
            allow_llm = False
        texts, source = await _explanations(results, cfg, allow_llm=allow_llm)
        conn.execute("delete from agent_suggestions where run_id = %s", [run_id])
        for horizon, result in results.items():
            result["explanation"] = texts.get(str(horizon), "")
            result["explanation_source"] = source
            alternatives = []
            if result.get("roll_alternative"):
                alternatives.append(result["roll_alternative"])
            if result.get("fewer_alternative"):
                alternatives.append(result["fewer_alternative"])
            conn.execute(
                """
                insert into agent_suggestions
                    (run_id, horizon, plan, alternatives, chip_advice, reason_codes, gain_vs_roll, hits, plan_hash, explanation, explanation_source)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    run_id,
                    int(horizon),
                    Json(result),
                    Json(alternatives),
                    Json(result.get("chips") or []),
                    result.get("reason_codes") or [],
                    result.get("gain_vs_roll"),
                    result.get("hits") or 0,
                    _plan_hash(result),
                    result.get("explanation"),
                    source,
                ],
            )
        finish_run(conn, run_id, ok=True)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        finish_run(conn, run_id, ok=False, error=str(exc))
        conn.commit()
        raise
