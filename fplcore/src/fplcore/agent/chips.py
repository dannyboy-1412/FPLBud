from __future__ import annotations

from typing import Any

from fplcore.optimise import PlayerOpt, SolvedPlan, optimise_horizon

BENCH_BOOST_THRESHOLD = 12.0
TRIPLE_CAPTAIN_THRESHOLD = 10.0
FREE_HIT_GAIN = 12.0
WILDCARD_GAIN = 20.0
EXPIRE_WITHIN = 3


def _chip_available(snapshot: dict[str, Any], name: str) -> dict[str, Any] | None:
    for chip in snapshot.get("chips_available") or []:
        if chip.get("name") == name:
            return chip
    return None


def _expire_warning(chip: dict[str, Any], next_gw: int) -> bool:
    stop = chip.get("stop_event")
    return stop is not None and stop - next_gw <= EXPIRE_WITHIN


def advise_chips(
    *,
    snapshot: dict[str, Any],
    best: SolvedPlan,
    players: list[PlayerOpt],
    bank: int,
    next_gw: int,
    horizon: int,
    weights_unused: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    by_id = {p.id: p for p in players}
    tips: list[dict[str, Any]] = []

    bb = _chip_available(snapshot, "bboost")
    if bb:
        best_gw = 1
        best_pts = 0.0
        for k in range(horizon):
            pts = sum(by_id[pid].proj[k] if pid in by_id and k < len(by_id[pid].proj) else 0.0 for pid in best.bench_ids)
            if pts > best_pts:
                best_pts, best_gw = pts, k + 1
            if sum(1 for pid in best.bench_ids if pid in by_id and k < len(by_id[pid].proj) and by_id[pid].proj[k] > 0) >= 2:
                # crude DGW: two bench players with proj (caller can pass fixture_count via proj=0 on blanks)
                pass
        for pid in best.bench_ids:
            if pid in by_id and len(by_id[pid].proj) > 0:
                # detect doubles from unusually high proj vs neighbours — skip; use fixture later
                pass
        recommend = "hold"
        if best_pts >= BENCH_BOOST_THRESHOLD:
            recommend = "play_now" if best_gw == 1 or horizon == 1 else f"consider_gw_{next_gw + best_gw - 1}"
        tips.append(
            {
                "chip": "bboost",
                "recommend": recommend if recommend != "hold" else "hold",
                "expected_gain": round(best_pts, 2),
                "reason_codes": ["CHIP_PLAY_NOW"] if recommend != "hold" else ["CHIP_HOLD"],
                "expires_soon": _expire_warning(bb, next_gw),
                "stop_event": bb.get("stop_event"),
            }
        )

    tc = _chip_available(snapshot, "3xc")
    if tc and best.captain_id in by_id:
        cap = by_id[best.captain_id]
        best_gw, best_pts = 1, cap.proj[0] if cap.proj else 0.0
        for k, pts in enumerate(cap.proj[:horizon]):
            if pts > best_pts:
                best_pts, best_gw = pts, k + 1
        recommend = "hold"
        if best_pts >= TRIPLE_CAPTAIN_THRESHOLD:
            recommend = "play_now" if best_gw == 1 or horizon == 1 else f"consider_gw_{next_gw + best_gw - 1}"
        tips.append(
            {
                "chip": "3xc",
                "recommend": recommend,
                "expected_gain": round(best_pts, 2),
                "reason_codes": ["CHIP_PLAY_NOW"] if recommend != "hold" else ["CHIP_HOLD"],
                "expires_soon": _expire_warning(tc, next_gw),
                "stop_event": tc.get("stop_event"),
            }
        )

    fh = _chip_available(snapshot, "freehit")
    if fh:
        selling_value = sum(snapshot.get("selling_prices", {}).get(str(pid), by_id[pid].sell) for pid in best.squad_ids if pid in by_id)
        try:
            fh_result = optimise_horizon(
                players,
                bank=selling_value + bank,
                free_transfers=15,
                horizon=1,
                max_hits=0,
                unlimited_transfers=True,
            )
            fh_best: SolvedPlan = fh_result["best"]
            gain = fh_best.projected_gw1 - best.projected_gw1
        except Exception:
            gain = 0.0
        blanks = sum(1 for pid in best.squad_ids if pid in by_id and (not by_id[pid].proj or by_id[pid].proj[0] == 0))
        recommend = "play_now" if gain >= FREE_HIT_GAIN or blanks >= 4 else "hold"
        tips.append(
            {
                "chip": "freehit",
                "recommend": recommend,
                "expected_gain": round(gain, 2),
                "reason_codes": ["CHIP_PLAY_NOW"] if recommend == "play_now" else ["CHIP_HOLD"],
                "expires_soon": _expire_warning(fh, next_gw),
                "stop_event": fh.get("stop_event"),
            }
        )

    wc = _chip_available(snapshot, "wildcard")
    if wc and horizon == 5:
        try:
            wc_result = optimise_horizon(
                players,
                bank=bank + sum(p.sell for p in players if p.in_squad) - sum(p.cost for p in players if p.in_squad),
                free_transfers=15,
                horizon=5,
                max_hits=0,
                unlimited_transfers=True,
            )
            wc_best: SolvedPlan = wc_result["best"]
            gain = wc_best.objective - best.objective
            wc_squad = wc_best.squad_ids
        except Exception:
            gain = 0.0
            wc_squad = []
        recommend = "play_now" if gain >= WILDCARD_GAIN else "hold"
        tips.append(
            {
                "chip": "wildcard",
                "recommend": recommend,
                "expected_gain": round(gain, 2),
                "reason_codes": ["CHIP_PLAY_NOW"] if recommend == "play_now" else ["CHIP_HOLD"],
                "expires_soon": _expire_warning(wc, next_gw),
                "stop_event": wc.get("stop_event"),
                "wildcard_squad": wc_squad,
            }
        )

    if horizon == 1:
        for tip in tips:
            if isinstance(tip["recommend"], str) and tip["recommend"].startswith("consider_"):
                tip["recommend"] = "play_now" if "CHIP_PLAY_NOW" in tip["reason_codes"] else "hold"

    return tips
