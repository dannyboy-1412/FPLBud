"""Pinned CONTEXT block. Built from stored snapshots, never a live FPL call."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, cast

from psycopg import Connection

from api.services import ranked_players
from fplcore.chat.prompt import ContextView, SquadRow
from fplcore.constants import DEFAULT_WEIGHTS, POSITION_SHORT
from fplcore.db import chat_repo
from fplcore.db.repos import current_season_id
from fplcore.db.stats_repo import started_gameweek, upcoming_gameweek

logger = logging.getLogger("fplbud.chat")

STALE_HOURS = 36


def pounds(tenths: object) -> float | None:
    if isinstance(tenths, bool) or not isinstance(tenths, int | float | str):
        return None
    return float(round(float(tenths) / 10, 1))


def build_context(conn: Connection, user_id: str, *, now: datetime | None = None) -> ContextView:
    moment = now or datetime.now(UTC)
    view = ContextView()
    season_id = _season(conn)
    view.season_id = season_id or ""
    version = _version(conn)
    if version is not None:
        view.data_version = int(version["id"])
        created = version.get("created_at")
        if isinstance(created, datetime):
            view.data_as_of = _iso(created)
            view.stale = (moment - _aware(created)).total_seconds() > STALE_HOURS * 3600
    if season_id:
        _apply_gameweeks(view, conn, season_id, moment)
    profile = chat_repo.profile_for_chat(conn, user_id) or {}
    weights = _weights(profile.get("weights"))
    view.weights = weights
    view.weights_are_default = weights == DEFAULT_WEIGHTS
    view.max_hits = int(profile.get("max_hits") or 1)
    horizon = int(profile.get("default_horizon") or 1)
    view.default_horizon = horizon if horizon in {1, 3, 5} else 1
    view.team_name = profile.get("fpl_team_name") or profile.get("display_name")
    snapshot = chat_repo.latest_snapshot(conn, user_id)
    view.has_team = snapshot is not None
    if snapshot is not None:
        _apply_snapshot(view, conn, snapshot, weights)
    _apply_plan(view, conn, user_id)
    view.prefs = [f"{row['key']}={row['value']}" for row in chat_repo.list_memory(conn, user_id)]
    return view


def fingerprint(view: ContextView) -> dict[str, Any]:
    return {
        "data_version": view.data_version,
        "data_as_of": view.data_as_of,
        "stale": view.stale,
        "deadline_utc": view.deadline_utc,
        "phase": view.phase,
        "hours_to_deadline": view.hours_to_deadline,
        "snapshot_id": view.snapshot_id,
        "snapshot_gw": view.snapshot_gw,
        "plan_headline": view.plan_headline,
        "flags": list(view.flags),
    }


def view_from_fingerprint(raw: dict[str, Any]) -> ContextView:
    return ContextView(
        data_version=raw.get("data_version"),
        data_as_of=raw.get("data_as_of"),
        stale=bool(raw.get("stale")),
        deadline_utc=raw.get("deadline_utc"),
        phase=str(raw.get("phase") or "between"),
        hours_to_deadline=raw.get("hours_to_deadline"),
        snapshot_id=raw.get("snapshot_id"),
        snapshot_gw=raw.get("snapshot_gw"),
        plan_headline=raw.get("plan_headline"),
        flags=list(raw.get("flags") or []),
    )


def _season(conn: Connection) -> str | None:
    try:
        return current_season_id(conn)
    except RuntimeError:
        return None


def _version(conn: Connection) -> dict[str, Any] | None:
    row = conn.execute(
        "select id, created_at from data_versions order by id desc limit 1"
    ).fetchone()
    return dict(row) if row is not None else None


def _apply_gameweeks(view: ContextView, conn: Connection, season_id: str, now: datetime) -> None:
    upcoming = upcoming_gameweek(conn, season_id, now)
    started = started_gameweek(conn, season_id, now)
    if upcoming:
        view.decision_gw = int(upcoming["id"])
        view.decision_name = str(upcoming.get("name") or f"GW {upcoming['id']}")
        deadline = upcoming.get("deadline_time")
        if isinstance(deadline, datetime):
            view.deadline_utc = _iso(deadline)
            view.hours_to_deadline = (_aware(deadline) - now).total_seconds() / 3600
            view.deadline_passed = view.hours_to_deadline < 0
        view.upcoming = [(int(upcoming["id"]), view.decision_name)]
    if started:
        view.started_gw = int(started["id"])
        view.started_finished = bool(started.get("finished"))
    if started and not started.get("finished"):
        view.phase = "live"
    elif view.hours_to_deadline is not None and view.hours_to_deadline >= 0:
        view.phase = "pre_deadline"
    else:
        view.phase = "between"


def _apply_snapshot(
    view: ContextView,
    conn: Connection,
    snapshot: dict[str, Any],
    weights: dict[str, float],
) -> None:
    view.snapshot_id = int(snapshot["id"])
    view.snapshot_gw = int(snapshot["event"])
    fetched = snapshot.get("fetched_at")
    view.snapshot_fetched_at = _iso(fetched) if isinstance(fetched, datetime) else None
    view.bank_m = pounds(snapshot.get("bank"))
    view.free_transfers = int(snapshot["free_transfers"])
    view.chips_available = _chip_names(snapshot.get("chips_available"))
    view.chips_used = _chip_names(snapshot.get("chips_used"))
    picks = list(snapshot.get("picks") or [])
    players = _players(conn, view.season_id, [int(pick["element"]) for pick in picks])
    ranked = _projections(conn, weights)
    starters: list[SquadRow] = []
    bench: list[SquadRow] = []
    for pick in sorted(picks, key=lambda item: int(item.get("position") or 99)):
        player_id = int(pick["element"])
        player = players.get(player_id, {})
        proj = ranked.get(player_id, {})
        row = SquadRow(
            player_id=player_id,
            name=str(player.get("web_name") or player_id),
            team=str(player.get("team_short") or ""),
            position=POSITION_SHORT.get(int(player.get("position_id") or 0), "?"),
            price_m=pounds(player.get("now_cost")) or 0.0,
            proj=float(proj.get("proj") or 0),
            status=str(player.get("status") or "a"),
            chance=player.get("chance_of_playing_next_round"),
        )
        view.names[player_id] = row.name
        slot = int(pick.get("position") or 0)
        if slot <= 11:
            starters.append(row)
        else:
            bench.append(row)
        if pick.get("is_captain"):
            view.captain_id = player_id
            view.captain_name = row.name
        if pick.get("is_vice_captain"):
            view.vice_id = player_id
            view.vice_name = row.name
        if row.status not in {"a", ""} or (row.chance is not None and int(row.chance) < 100):
            news = str(player.get("news") or "")[:80]
            view.flags.append(f"{player_id} {row.name} {row.status} {row.chance if row.chance is not None else ''} {news}".strip())
    view.starters = starters
    view.bench = bench


def _apply_plan(view: ContextView, conn: Connection, user_id: str) -> None:
    found = conn.execute(
        """
        select r.data_version, s.plan->>'headline' as headline, s.explanation
          from agent_runs r
          join agent_suggestions s on s.run_id = r.id and s.horizon = 1
         where r.user_id = %s and r.status = 'succeeded'
         order by r.finished_at desc nulls last
         limit 1
        """,
        [user_id],
    ).fetchone()
    if found is None:
        return
    row = cast(dict[str, Any], found)
    headline = row["headline"] or ""
    if not headline and row["explanation"]:
        headline = str(row["explanation"]).split(".")[0]
    view.plan_headline = str(headline)[:180] or None
    if view.data_version is not None and row["data_version"] is not None:
        view.plan_fresh = int(row["data_version"]) == int(view.data_version)


def _players(conn: Connection, season_id: str, ids: list[int]) -> dict[int, dict[str, Any]]:
    if not season_id or not ids:
        return {}
    rows = conn.execute(
        """
        select p.id, p.web_name, p.position_id, p.now_cost, p.status,
               p.chance_of_playing_next_round, p.news, t.short_name as team_short
          from players p
          join teams t on t.season_id = p.season_id and t.id = p.team_id
         where p.season_id = %s and p.id = any(%s)
        """,
        [season_id, ids],
    ).fetchall()
    return {int(cast(dict[str, Any], row)["id"]): cast(dict[str, Any], row) for row in rows}


def _projections(conn: Connection, weights: dict[str, float]) -> dict[int, dict[str, Any]]:
    try:
        ranked = ranked_players(conn, weights=weights, horizon=1)
    except Exception:
        logger.exception("chat projections unavailable")
        return {}
    return {int(row["id"]): row for row in ranked}


def _weights(raw: object) -> dict[str, float]:
    if not isinstance(raw, dict) or not raw:
        return dict(DEFAULT_WEIGHTS)
    weights: dict[str, float] = {}
    for key, value in raw.items():
        try:
            weights[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return weights or dict(DEFAULT_WEIGHTS)


def _chip_names(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def _iso(value: datetime) -> str:
    return _aware(value).isoformat()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
