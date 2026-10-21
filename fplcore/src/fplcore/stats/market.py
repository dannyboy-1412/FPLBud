from __future__ import annotations

from typing import Any

from fplcore.constants import STATS_TOP_N


def player_card(row: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    card: dict[str, Any] = {
        "id": int(row["id"]),
        "web_name": row["web_name"],
        "team_short": row["team_short"],
        "position_id": int(row["position_id"]),
        "now_cost": int(row["now_cost"]),
        "selected_by_percent": float(row["selected_by_percent"]),
    }
    if extra:
        card.update(extra)
    return card


def top_transfers(players: list[dict[str, Any]], *, n: int = STATS_TOP_N) -> dict[str, list[dict[str, Any]]]:
    def pack(row: dict[str, Any]) -> dict[str, Any]:
        tin = int(row["transfers_in_event"])
        tout = int(row["transfers_out_event"])
        return player_card(row, {"transfers_in_event": tin, "transfers_out_event": tout, "net": tin - tout})

    ins = sorted(players, key=lambda p: int(p["transfers_in_event"]), reverse=True)[:n]
    outs = sorted(players, key=lambda p: int(p["transfers_out_event"]), reverse=True)[:n]
    return {"top_in": [pack(r) for r in ins], "top_out": [pack(r) for r in outs]}


def price_movers(players: list[dict[str, Any]], *, n: int = STATS_TOP_N) -> dict[str, list[dict[str, Any]]]:
    def pack(row: dict[str, Any]) -> dict[str, Any]:
        return player_card(
            row,
            {
                "cost_change_event": int(row["cost_change_event"]),
                "cost_change_start": int(row["cost_change_start"]),
                "daily_change": int(row.get("daily_change") or 0),
            },
        )

    risers = sorted(
        (p for p in players if int(p["cost_change_event"]) > 0),
        key=lambda p: int(p["cost_change_event"]),
        reverse=True,
    )[:n]
    fallers = sorted(
        (p for p in players if int(p["cost_change_event"]) < 0),
        key=lambda p: int(p["cost_change_event"]),
    )[:n]
    return {"risers": [pack(r) for r in risers], "fallers": [pack(r) for r in fallers]}


def movers_24h(
    players: list[dict[str, Any]],
    yesterday: dict[int, dict[str, Any]],
    *,
    n: int = STATS_TOP_N,
) -> list[dict[str, Any]]:
    if not yesterday:
        return []
    rows: list[dict[str, Any]] = []
    for player in players:
        prev = yesterday.get(int(player["id"]))
        if not prev:
            continue
        net_today = int(player["transfers_in_event"]) - int(player["transfers_out_event"])
        net_yday = int(prev["transfers_in_event"]) - int(prev["transfers_out_event"])
        daily_change = int(player["now_cost"]) - int(prev["now_cost"])
        rows.append(
            player_card(player, {"net_24h": net_today - net_yday, "daily_change": daily_change})
        )
    rows.sort(key=lambda r: abs(int(r["net_24h"])), reverse=True)
    return rows[:n]


def price_pressure(
    players: list[dict[str, Any]],
    total_managers: int,
    *,
    n: int = STATS_TOP_N,
) -> dict[str, list[dict[str, Any]]]:
    scored: list[dict[str, Any]] = []
    for player in players:
        owners = float(player["selected_by_percent"]) * total_managers / 100.0
        if owners < 1:
            continue
        net = int(player["transfers_in_event"]) - int(player["transfers_out_event"])
        scored.append(
            player_card(
                player,
                {"net": net, "owners": int(owners), "pressure": round(net / owners, 4)},
            )
        )
    rise = sorted(scored, key=lambda r: float(r["pressure"]), reverse=True)[:n]
    fall = sorted(scored, key=lambda r: float(r["pressure"]))[:n]
    return {"likely_to_rise": rise, "likely_to_fall": fall}
