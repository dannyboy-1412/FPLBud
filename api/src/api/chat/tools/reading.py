"""Shared reads for chat tools: the saved squad, the data stamp, and fixture lists."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fplcore.chat.cache import current_cache
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.db import chat_repo
from fplcore.team_import import TeamSnapshot, apply_overrides, snapshot_from_row


def user_snapshot(ctx: ToolContext, conn: Any) -> TeamSnapshot | None:
    if not ctx.has_team:
        return None
    stored = chat_repo.latest_snapshot(conn, ctx.user_id)
    if stored is None:
        return None
    return apply_overrides(snapshot_from_row(stored), stored.get("overrides"))


def no_team() -> ToolResult:
    return failure(
        "NO_TEAM_SAVED",
        "Save a team on the dashboard first.",
        hint="Personalised tools need a saved squad.",
    )


def lookup_as_of(conn: Any) -> str | None:
    cache = current_cache()
    if cache is not None and cache.as_of_loaded:
        return cache.as_of
    stamp = _read_as_of(conn)
    if cache is not None:
        cache.as_of = stamp
        cache.as_of_loaded = True
    return stamp


def matches_by_team(fixtures: list[dict[str, Any]]) -> dict[int, dict[int, list[dict[str, Any]]]]:
    grouped: dict[int, dict[int, list[dict[str, Any]]]] = {}
    for row in fixtures:
        event = row.get("event")
        if event is None:
            continue
        gw = int(event)
        home = {
            "opponent": row.get("away_short"),
            "fdr": int(row["team_h_difficulty"]),
            "home": True,
        }
        away = {
            "opponent": row.get("home_short"),
            "fdr": int(row["team_a_difficulty"]),
            "home": False,
        }
        grouped.setdefault(int(row["team_h"]), {}).setdefault(gw, []).append(home)
        grouped.setdefault(int(row["team_a"]), {}).setdefault(gw, []).append(away)
    return grouped


def with_matches(
    by_gw: list[dict[str, Any]],
    team_id: int,
    lookup: dict[int, dict[int, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    team = lookup.get(team_id, {})
    decorated: list[dict[str, Any]] = []
    for item in by_gw:
        gw = int(item["gw"])
        decorated.append({**item, "matches": team.get(gw, [])})
    return decorated


def _read_as_of(conn: Any) -> str | None:
    if conn is None:
        return None
    row = conn.execute(
        "select computed_at from player_metrics order by computed_at desc limit 1"
    ).fetchone()
    if row is not None and row["computed_at"] is not None:
        return _iso(row["computed_at"])
    row = conn.execute(
        """
        select finished_at from ingest_runs
         where ok = true and finished_at is not null
         order by finished_at desc
         limit 1
        """
    ).fetchone()
    if row is not None and row["finished_at"] is not None:
        return _iso(row["finished_at"])
    return None


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
