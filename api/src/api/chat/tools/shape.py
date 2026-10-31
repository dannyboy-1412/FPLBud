from __future__ import annotations

from typing import Any

from api.chat.context import pounds


def compact_player(row: dict[str, Any]) -> dict[str, Any]:
    price = pounds(row["now_cost"]) if row.get("now_cost") is not None else row.get("price_m")
    return {
        "id": row.get("id") or row.get("player_id"),
        "name": row.get("web_name") or row.get("name"),
        "team": row.get("team_short") or row.get("team"),
        "position_id": row.get("position_id"),
        "price_m": price,
        "proj": row.get("proj"),
        "own": row.get("selected_by_percent"),
        "status": row.get("status"),
    }


def take(rows: list[Any], limit: int = 5) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows[:limit]:
        if isinstance(row, dict):
            compact.append(compact_player(row))
    return compact
