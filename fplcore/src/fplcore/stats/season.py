from __future__ import annotations

from typing import Any

from fplcore.models import ChipUsed, EntryHistoryRow

_TRIPLE = {"3xc", "triple_captain"}


def season_rows(
    history: list[EntryHistoryRow],
    gameweeks: dict[int, dict[str, Any]],
    chips: list[ChipUsed],
) -> list[dict[str, Any]]:
    chip_by_event = {chip.event: chip.name for chip in chips}
    rows: list[dict[str, Any]] = []
    for row in history:
        gw = gameweeks.get(row.event) or {}
        avg = gw.get("average_entry_score")
        avg_int = int(avg) if avg is not None else None
        rows.append(
            {
                "event": row.event,
                "points": row.points,
                "total_points": row.total_points,
                "average": avg_int,
                "delta_vs_avg": (row.points - avg_int) if avg_int is not None else None,
                "highest": gw.get("highest_score"),
                "rank": row.rank,
                "overall_rank": row.overall_rank,
                "percentile_rank": row.percentile_rank,
                "points_on_bench": row.points_on_bench,
                "transfers": row.event_transfers,
                "hit_cost": row.event_transfers_cost,
                "value": row.value,
                "chip": chip_by_event.get(row.event),
            }
        )
    return rows


def season_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "best_gw": None,
            "worst_gw": None,
            "gws_above_average": 0,
            "bench_points_total": 0,
            "hit_cost_total": 0,
            "latest_percentile": None,
            "latest_overall_rank": None,
            "total_points": 0,
        }
    best = max(rows, key=lambda r: int(r["points"]))
    worst = min(rows, key=lambda r: int(r["points"]))
    last = rows[-1]
    return {
        "best_gw": {"event": best["event"], "points": best["points"]},
        "worst_gw": {"event": worst["event"], "points": worst["points"]},
        "gws_above_average": sum(
            1 for r in rows if r["delta_vs_avg"] is not None and int(r["delta_vs_avg"]) > 0
        ),
        "bench_points_total": sum(int(r["points_on_bench"] or 0) for r in rows),
        "hit_cost_total": sum(int(r["hit_cost"] or 0) for r in rows),
        "latest_percentile": last.get("percentile_rank"),
        "latest_overall_rank": last.get("overall_rank"),
        "total_points": int(last.get("total_points") or 0),
    }


def captain_returns(
    history: list[EntryHistoryRow],
    picks_by_event: dict[int, dict[str, Any]],
    points_by_player_event: dict[tuple[int, int], int],
    names: dict[int, str],
    most_captained: dict[int, int | None],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in history:
        payload = picks_by_event.get(row.event)
        if not payload:
            continue
        picks = payload.get("picks") or []
        captain = next((p for p in picks if p.get("is_captain")), None)
        if not captain:
            continue
        captain_id = int(captain["element"])
        multiplier = int(captain.get("multiplier") or 0)
        chip = (payload.get("active_chip") or "")
        if chip in _TRIPLE:
            multiplier = max(multiplier, 3)
        elif multiplier <= 0:
            multiplier = 2
        raw = points_by_player_event.get((captain_id, row.event), 0)
        yours = raw * multiplier
        crowd_id = most_captained.get(row.event)
        crowd_raw = points_by_player_event.get((crowd_id, row.event), 0) if crowd_id else 0
        crowd_pts = crowd_raw * 2
        rows.append(
            {
                "event": row.event,
                "captain_id": captain_id,
                "captain_name": names.get(captain_id, str(captain_id)),
                "multiplier": multiplier,
                "points": yours,
                "crowd_id": crowd_id,
                "crowd_name": names.get(crowd_id, str(crowd_id)) if crowd_id else None,
                "crowd_points": crowd_pts,
                "delta": yours - crowd_pts,
            }
        )
    return {
        "rows": rows,
        "total": sum(int(r["points"]) for r in rows),
        "crowd_total": sum(int(r["crowd_points"]) for r in rows),
    }
