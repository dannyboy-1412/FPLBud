from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pulp

from fplcore.constants import PREFILTER_PER_POSITION, SQUAD_MAX_PLAY, SQUAD_MIN_PLAY, SQUAD_SELECT


@dataclass(frozen=True)
class HorizonSettings:
    n: int
    delta: float
    hit_margin: float
    roll_value: float
    max_hits_default: int


HORIZON_SETTINGS = {
    1: HorizonSettings(n=1, delta=0.85, hit_margin=2.0, roll_value=2.0, max_hits_default=1),
    3: HorizonSettings(n=3, delta=0.85, hit_margin=1.0, roll_value=1.0, max_hits_default=1),
    5: HorizonSettings(n=5, delta=0.85, hit_margin=0.5, roll_value=0.5, max_hits_default=2),
}


@dataclass
class PlayerOpt:
    id: int
    web_name: str
    team_id: int
    position_id: int
    cost: int
    sell: int
    in_squad: bool
    can_in: bool
    locked: bool
    proj: list[float]
    scores_gw1: dict[str, float]


@dataclass
class TransferMove:
    out_id: int
    in_id: int
    out_name: str
    in_name: str
    cost_delta: int
    metric_deltas: dict[str, float]


@dataclass
class SolvedPlan:
    transfers_in: int
    hits: int
    objective: float
    projected_gw1: float
    squad_ids: list[int]
    xi_ids: list[int]
    bench_ids: list[int]
    captain_id: int | None
    vice_id: int | None
    bank_after: int
    moves: list[TransferMove] = field(default_factory=list)
    projected_points_by_gw: dict[int, float] = field(default_factory=dict)


def _prefilter(players: list[PlayerOpt], current_ids: set[int]) -> list[PlayerOpt]:
    kept: list[PlayerOpt] = []
    by_pos: dict[int, list[PlayerOpt]] = {1: [], 2: [], 3: [], 4: []}
    for player in players:
        if player.in_squad or player.locked:
            kept.append(player)
        else:
            by_pos[player.position_id].append(player)
    for pos_players in by_pos.values():
        pos_players.sort(key=lambda p: p.proj[0] if p.proj else 0.0, reverse=True)
        kept.extend(pos_players[:PREFILTER_PER_POSITION])
    seen = {p.id for p in kept}
    for player in players:
        if player.id in current_ids and player.id not in seen:
            kept.append(player)
    return kept


def _pair_transfers(
    current: set[int],
    new_squad: set[int],
    by_id: dict[int, PlayerOpt],
) -> list[TransferMove]:
    outs = [pid for pid in current if pid not in new_squad]
    ins = [pid for pid in new_squad if pid not in current]
    outs.sort(key=lambda pid: by_id[pid].position_id if pid in by_id else 0)
    ins.sort(key=lambda pid: by_id[pid].position_id if pid in by_id else 0)
    moves: list[TransferMove] = []
    for out_id, in_id in zip(outs, ins, strict=False):
        out_p, in_p = by_id[out_id], by_id[in_id]
        deltas = {
            key: round(in_p.scores_gw1.get(key, 0.0) - out_p.scores_gw1.get(key, 0.0), 4)
            for key in sorted(set(out_p.scores_gw1) | set(in_p.scores_gw1))
        }
        moves.append(
            TransferMove(
                out_id=out_id,
                in_id=in_id,
                out_name=out_p.web_name,
                in_name=in_p.web_name,
                cost_delta=in_p.cost - out_p.sell,
                metric_deltas=deltas,
            )
        )
    return moves


def solve_for_transfers(
    players: list[PlayerOpt],
    *,
    bank: int,
    free_transfers: int,
    transfers_in_target: int,
    horizon: int,
    delta: float,
    team_limit: int = 3,
    time_limit: int = 8,
) -> SolvedPlan | None:
    by_id = {p.id: p for p in players}
    current = {p.id for p in players if p.in_squad}
    prob = pulp.LpProblem(f"fpl_n{horizon}_t{transfers_in_target}", pulp.LpMaximize)

    x = {p.id: pulp.LpVariable(f"x_{p.id}", cat="Binary") for p in players}
    inn = {p.id: pulp.LpVariable(f"in_{p.id}", cat="Binary") for p in players}
    out = {p.id: pulp.LpVariable(f"out_{p.id}", cat="Binary") for p in players}
    s = {p.id: pulp.LpVariable(f"s_{p.id}", cat="Binary") for p in players}
    c = {p.id: pulp.LpVariable(f"c_{p.id}", cat="Binary") for p in players}
    h = pulp.LpVariable("h", lowBound=0, upBound=max(0, transfers_in_target - free_transfers), cat="Integer")

    obj = []
    for p in players:
        proj = p.proj + [0.0] * max(0, horizon - len(p.proj))
        obj.append(proj[0] * (s[p.id] + c[p.id] + 0.1 * (x[p.id] - s[p.id])))
        for k in range(1, horizon):
            obj.append((delta**k) * proj[k] * x[p.id])
    obj.append(-4 * h)
    prob += pulp.lpSum(obj)

    prob += pulp.lpSum(inn[p.id] for p in players) == transfers_in_target
    for p in players:
        in_current = 1 if p.in_squad else 0
        prob += x[p.id] == in_current + inn[p.id] - out[p.id]
        if p.in_squad:
            prob += inn[p.id] == 0
            if p.locked:
                prob += out[p.id] == 0
        else:
            prob += out[p.id] == 0
            if not p.can_in:
                prob += inn[p.id] == 0
        prob += s[p.id] <= x[p.id]
        prob += c[p.id] <= s[p.id]

    prob += pulp.lpSum(x[p.id] for p in players) == 15
    for pos, count in SQUAD_SELECT.items():
        prob += pulp.lpSum(x[p.id] for p in players if p.position_id == pos) == count

    clubs = {p.team_id for p in players}
    for club in clubs:
        prob += pulp.lpSum(x[p.id] for p in players if p.team_id == club) <= team_limit

    prob += pulp.lpSum(inn[p.id] * p.cost for p in players) <= bank + pulp.lpSum(out[p.id] * p.sell for p in players)
    prob += pulp.lpSum(inn[p.id] for p in players) - free_transfers <= h

    prob += pulp.lpSum(s[p.id] for p in players) == 11
    for pos, minimum in SQUAD_MIN_PLAY.items():
        prob += pulp.lpSum(s[p.id] for p in players if p.position_id == pos) >= minimum
    for pos, maximum in SQUAD_MAX_PLAY.items():
        prob += pulp.lpSum(s[p.id] for p in players if p.position_id == pos) <= maximum
    prob += pulp.lpSum(c[p.id] for p in players) == 1

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, options=["ratio", "0.02"]))
    if pulp.LpStatus[status] not in {"Optimal", "Not Solved"}:
        if pulp.value(prob.objective) is None:
            return None
    if pulp.LpStatus[status] == "Infeasible":
        return None

    squad_ids = [pid for pid, var in x.items() if var.value() and var.value() > 0.5]
    xi_ids = [pid for pid, var in s.items() if var.value() and var.value() > 0.5]
    captain_id = next((pid for pid, var in c.items() if var.value() and var.value() > 0.5), None)
    bench_ids = [pid for pid in squad_ids if pid not in xi_ids]
    bench_ids.sort(key=lambda pid: (-(1 if by_id[pid].position_id == 1 else 0), -(by_id[pid].proj[0] if by_id[pid].proj else 0)))
    xi_sorted = sorted(xi_ids, key=lambda pid: by_id[pid].position_id)
    vice_id = None
    if captain_id is not None:
        others = sorted(
            [pid for pid in xi_ids if pid != captain_id],
            key=lambda pid: by_id[pid].proj[0] if by_id[pid].proj else 0,
            reverse=True,
        )
        vice_id = others[0] if others else None

    hits = int(round(h.value() or 0))
    spend = sum(by_id[pid].cost for pid in squad_ids if pid not in current)
    proceeds = sum(by_id[pid].sell for pid in current if pid not in set(squad_ids))
    bank_after = bank + proceeds - spend

    gw_proj: dict[int, float] = {}
    for k in range(horizon):
        gw_proj[k + 1] = round(sum((by_id[pid].proj[k] if k < len(by_id[pid].proj) else 0.0) for pid in squad_ids), 2)

    gw1 = 0.0
    for pid in xi_ids:
        gw1 += by_id[pid].proj[0] if by_id[pid].proj else 0.0
    if captain_id is not None and captain_id in by_id:
        gw1 += by_id[captain_id].proj[0] if by_id[captain_id].proj else 0.0
    for pid in bench_ids:
        gw1 += 0.1 * (by_id[pid].proj[0] if by_id[pid].proj else 0.0)

    return SolvedPlan(
        transfers_in=transfers_in_target,
        hits=hits,
        objective=float(pulp.value(prob.objective) or 0.0),
        projected_gw1=round(gw1, 3),
        squad_ids=squad_ids,
        xi_ids=xi_sorted,
        bench_ids=bench_ids,
        captain_id=captain_id,
        vice_id=vice_id,
        bank_after=bank_after,
        moves=_pair_transfers(current, set(squad_ids), by_id),
        projected_points_by_gw=gw_proj,
    )


def pick_best_plan(
    plans: dict[int, SolvedPlan],
    *,
    free_transfers: int,
    settings: HorizonSettings,
    max_hits: int,
) -> tuple[SolvedPlan, SolvedPlan | None, SolvedPlan | None]:
    roll = plans.get(0)
    if roll is None:
        raise ValueError("roll plan (0 transfers) is required")

    def adjusted(plan: SolvedPlan) -> float:
        unused_ft = max(0, free_transfers - plan.transfers_in)
        return plan.objective + settings.roll_value * unused_ft

    roll_adj = adjusted(roll)
    eligible: list[SolvedPlan] = [roll]
    for k, plan in plans.items():
        if k == 0:
            continue
        if plan.hits > max_hits:
            continue
        extra = adjusted(plan) - roll_adj
        if plan.hits == 0 or extra >= 4 + settings.hit_margin:
            eligible.append(plan)
    best = max(eligible, key=adjusted)
    fewer = None
    if best.transfers_in > 0:
        candidates = [p for k, p in plans.items() if 0 < k < best.transfers_in]
        if candidates:
            fewer = max(candidates, key=adjusted)
    return best, roll, fewer


def optimise_horizon(
    players: list[PlayerOpt],
    *,
    bank: int,
    free_transfers: int,
    horizon: int,
    max_hits: int | None = None,
    lock_ids: list[int] | None = None,
    exclude_ids: list[int] | None = None,
    unlimited_transfers: bool = False,
) -> dict[str, Any]:
    settings = HORIZON_SETTINGS.get(horizon) or HorizonSettings(
        n=horizon, delta=0.85, hit_margin=1.0, roll_value=1.0, max_hits_default=1
    )
    hits_cap = settings.max_hits_default if max_hits is None else max_hits
    locks = set(lock_ids or [])
    excludes = set(exclude_ids or [])
    prepared: list[PlayerOpt] = []
    for player in players:
        prepared.append(
            PlayerOpt(
                **{
                    **player.__dict__,
                    "locked": player.id in locks,
                    "can_in": player.can_in and player.id not in excludes,
                }
            )
        )
    current_ids = {p.id for p in prepared if p.in_squad}
    filtered = _prefilter(prepared, current_ids)
    ft = 15 if unlimited_transfers else free_transfers
    max_in = 15 if unlimited_transfers else min(15, ft + hits_cap)
    plans: dict[int, SolvedPlan] = {}
    for k in range(0, max_in + 1):
        solved = solve_for_transfers(
            filtered,
            bank=bank,
            free_transfers=ft,
            transfers_in_target=k,
            horizon=settings.n,
            delta=settings.delta,
        )
        if solved is not None:
            plans[k] = solved
    if 0 not in plans:
        raise RuntimeError("Unable to solve the roll (0-transfer) plan")
    best, roll, fewer = pick_best_plan(plans, free_transfers=ft, settings=settings, max_hits=hits_cap)
    return {
        "best": best,
        "roll": roll,
        "fewer": fewer,
        "all": plans,
        "settings": settings,
    }
