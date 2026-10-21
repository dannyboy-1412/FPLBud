from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from psycopg import Connection

from api.auth import current_user, optional_user
from api.deps import db_conn, get_settings_dep
from api.limiter import limiter
from api.services import (
    insights_payload,
    load_merged_entry,
    market_payload,
    season_stats_payload,
    squad_stats_payload,
)
from api.weights_query import parse_weights_query
from fplcore.client import FplClient, FplNotFoundError
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db import stats_repo
from fplcore.models import EntryHistory
from fplcore.settings import Settings

router = APIRouter()


@router.get("/stats/market")
def market(conn: Connection = Depends(db_conn)) -> dict:
    return market_payload(conn)


@router.get("/stats/insights")
def insights(
    position: int | None = Query(default=None, ge=1, le=4),
    weights: str | None = Query(default=None),
    user: dict | None = Depends(optional_user),
    conn: Connection = Depends(db_conn),
) -> dict:
    parsed = parse_weights_query(weights)
    if parsed is not None:
        resolved = parsed
    elif user:
        row = conn.execute(
            "select weights from public.profiles where id = %s", [user["id"]]
        ).fetchone()
        resolved = dict(row["weights"]) if row else dict(DEFAULT_WEIGHTS)
    else:
        resolved = dict(DEFAULT_WEIGHTS)
    return insights_payload(conn, weights=resolved, position=position)


@router.get("/me/stats/squad")
async def my_squad(
    user: dict = Depends(current_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    profile = conn.execute("select * from public.profiles where id = %s", [user["id"]]).fetchone()
    if profile is None or not profile["fpl_entry_id"]:
        raise HTTPException(status_code=400, detail="save a team id first")
    try:
        async with FplClient(settings) as client:
            payload, _bootstrap = await load_merged_entry(conn, client, int(profile["fpl_entry_id"]))
    except FplNotFoundError:
        raise HTTPException(status_code=404, detail="team not found") from None
    return squad_stats_payload(conn, {"picks": payload["picks"]["picks"]}, dict(profile["weights"]))


@router.get("/me/stats/season")
@limiter.limit("10/minute")
async def my_season(
    request: Request,
    user: dict = Depends(current_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    profile = conn.execute("select * from public.profiles where id = %s", [user["id"]]).fetchone()
    if profile is None or not profile["fpl_entry_id"]:
        raise HTTPException(status_code=400, detail="save a team id first")
    entry_id = int(profile["fpl_entry_id"])
    try:
        async with FplClient(settings) as client:
            payload, _bootstrap = await load_merged_entry(conn, client, entry_id)
            history = EntryHistory.model_validate(payload["history"])
            finished = [row.event for row in history.current]
            missing = stats_repo.missing_entry_events(conn, entry_id, finished)
            picks_by_event = stats_repo.get_entry_event_picks(conn, entry_id, finished)
            for event in missing:
                try:
                    picks = await client.entry_picks(entry_id, event)
                except FplNotFoundError:
                    continue
                dump = [p.model_dump(mode="json") for p in picks.picks]
                stats_repo.put_entry_event_picks(conn, entry_id, event, dump, picks.active_chip)
                picks_by_event[event] = {"picks": dump, "active_chip": picks.active_chip}
            conn.commit()
    except FplNotFoundError:
        raise HTTPException(status_code=404, detail="team not found") from None

    captain_ids: list[int] = []
    for _event, stored in picks_by_event.items():
        for pick in stored.get("picks") or []:
            if pick.get("is_captain"):
                captain_ids.append(int(pick["element"]))
    gameweeks = stats_repo.gameweek_meta_rows(conn)
    crowd_ids = [int(g["most_captained"]) for g in gameweeks if g.get("most_captained")]
    ids = list({*captain_ids, *crowd_ids})
    names = stats_repo.player_names(conn, ids)
    points = stats_repo.player_round_points(conn, ids, finished)
    return season_stats_payload(history, gameweeks, picks_by_event, points, names)
