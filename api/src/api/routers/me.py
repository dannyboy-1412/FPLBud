from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from psycopg import Connection
from psycopg.types.json import Json
from pydantic import BaseModel, Field

from api.auth import current_user
from api.deps import db_conn, get_settings_dep
from api.limiter import limiter
from api.services import (
    build_suggested_transfers,
    build_suggested_xi,
    load_merged_entry,
    snapshot_from_cache,
)
from api.worker import kickoff
from fplcore.agent.queue import enqueue_run
from fplcore.client import FplClient, FplNotFoundError
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import current_season_id, save_snapshot
from fplcore.settings import Settings

router = APIRouter()


class MeUpdate(BaseModel):
    weights: dict[str, float] | None = None
    default_horizon: int | None = Field(default=None, ge=1, le=5)
    max_hits: int | None = Field(default=None, ge=0, le=3)


class TeamBody(BaseModel):
    entry_id: int = Field(gt=0)


class ImportBody(BaseModel):
    overrides: dict[str, Any] | None = None


def _latest_run_id(conn: Connection, user_id: Any, entry_id: int | None) -> int | None:
    row = conn.execute(
        """
        select id from agent_runs
         where user_id = %s and (%s::int is null or entry_id = %s)
         order by created_at desc limit 1
        """,
        [user_id, entry_id, entry_id],
    ).fetchone()
    return int(row["id"]) if row else None


@router.get("/me")
def get_me(user: dict = Depends(current_user), conn: Connection = Depends(db_conn)) -> dict:
    profile = conn.execute("select * from public.profiles where id = %s", [user["id"]]).fetchone()
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    snapshot = None
    if profile["fpl_entry_id"]:
        snapshot = conn.execute(
            """
            select * from team_snapshots
             where created_by = %s and entry_id = %s
             order by fetched_at desc limit 1
            """,
            [user["id"], profile["fpl_entry_id"]],
        ).fetchone()
    return {
        "profile": dict(profile),
        "snapshot": dict(snapshot) if snapshot else None,
        "latest_run_id": _latest_run_id(conn, user["id"], profile["fpl_entry_id"]),
    }


@router.post("/me/suggested-xi")
@limiter.limit("6/hour")
async def suggested_xi(
    request: Request,
    user: dict = Depends(current_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    return await build_suggested_xi(conn, settings, user["id"])


@router.post("/me/suggested-transfers")
@limiter.limit("6/hour")
async def suggested_transfers(
    request: Request,
    user: dict = Depends(current_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    return await build_suggested_transfers(conn, settings, user["id"])


@router.put("/me")
@limiter.limit("30/minute")
def put_me(
    request: Request,
    body: MeUpdate,
    background: BackgroundTasks,
    user: dict = Depends(current_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    profile = conn.execute("select * from public.profiles where id = %s", [user["id"]]).fetchone()
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    weights = body.weights if body.weights is not None else profile["weights"]
    horizon = body.default_horizon if body.default_horizon is not None else profile["default_horizon"]
    max_hits = body.max_hits if body.max_hits is not None else profile["max_hits"]
    conn.execute(
        """
        update public.profiles
           set weights = %s, default_horizon = %s, max_hits = %s
         where id = %s
        """,
        [Json(weights), horizon, max_hits, user["id"]],
    )
    rerun_id = None
    if body.weights is not None and profile["fpl_entry_id"]:
        snap = conn.execute(
            """
            select id from team_snapshots
             where created_by = %s and entry_id = %s
             order by fetched_at desc limit 1
            """,
            [user["id"], profile["fpl_entry_id"]],
        ).fetchone()
        version = conn.execute("select id from data_versions order by id desc limit 1").fetchone()
        if snap:
            run = enqueue_run(
                conn,
                user_id=user["id"],
                entry_id=int(profile["fpl_entry_id"]),
                snapshot_id=int(snap["id"]),
                trigger="user_rerun",
                weights=weights,
                data_version=int(version["id"]) if version else None,
            )
            rerun_id = int(run["id"])
            background.add_task(kickoff, settings)
    conn.commit()
    return {"ok": True, "run_id": rerun_id}


@router.put("/me/team")
@limiter.limit("30/minute")
async def put_team(
    request: Request,
    body: TeamBody,
    background: BackgroundTasks,
    user: dict = Depends(current_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    try:
        async with FplClient(settings) as client:
            payload, bootstrap = await load_merged_entry(conn, client, body.entry_id)
    except FplNotFoundError:
        raise HTTPException(status_code=404, detail="team not found") from None
    season_id = current_season_id(conn)
    snapshot = snapshot_from_cache(payload, bootstrap, season_id)
    stored = save_snapshot(conn, snapshot, user["id"])
    conn.execute(
        """
        insert into tracked_entries (user_id, entry_id) values (%s, %s)
        on conflict (user_id, entry_id) do nothing
        """,
        [user["id"], body.entry_id],
    )
    conn.execute(
        """
        update public.profiles
           set fpl_entry_id = %s, fpl_team_name = %s, onboarded_at = coalesce(onboarded_at, now())
         where id = %s
        """,
        [body.entry_id, snapshot.name, user["id"]],
    )
    profile = conn.execute("select weights from public.profiles where id = %s", [user["id"]]).fetchone()
    version = conn.execute("select id from data_versions order by id desc limit 1").fetchone()
    run = enqueue_run(
        conn,
        user_id=user["id"],
        entry_id=body.entry_id,
        snapshot_id=int(stored["id"]),
        trigger="import",
        weights=profile["weights"] if profile else DEFAULT_WEIGHTS,
        data_version=int(version["id"]) if version else None,
    )
    conn.commit()
    background.add_task(kickoff, settings)
    return {"snapshot": snapshot.to_payload(), "run_id": int(run["id"]), "status": run["status"]}


@router.post("/me/team/import", status_code=202)
@limiter.limit("30/minute")
async def import_team(
    request: Request,
    body: ImportBody,
    background: BackgroundTasks,
    user: dict = Depends(current_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    profile = conn.execute("select * from public.profiles where id = %s", [user["id"]]).fetchone()
    if not profile or not profile["fpl_entry_id"]:
        raise HTTPException(status_code=400, detail="save a team id first")
    try:
        async with FplClient(settings) as client:
            payload, bootstrap = await load_merged_entry(conn, client, int(profile["fpl_entry_id"]))
    except FplNotFoundError:
        raise HTTPException(status_code=404, detail="team not found") from None
    season_id = current_season_id(conn)
    snapshot = snapshot_from_cache(payload, bootstrap, season_id, body.overrides)
    stored = save_snapshot(conn, snapshot, user["id"])
    if body.overrides:
        conn.execute(
            "update tracked_entries set overrides = %s where user_id = %s and entry_id = %s",
            [Json(body.overrides), user["id"], profile["fpl_entry_id"]],
        )
    version = conn.execute("select id from data_versions order by id desc limit 1").fetchone()
    run = enqueue_run(
        conn,
        user_id=user["id"],
        entry_id=int(profile["fpl_entry_id"]),
        snapshot_id=int(stored["id"]),
        trigger="import",
        weights=profile["weights"],
        data_version=int(version["id"]) if version else None,
    )
    conn.commit()
    background.add_task(kickoff, settings)
    return {"snapshot": snapshot.to_payload(), "run_id": int(run["id"]), "status": run["status"]}


@router.delete("/me")
async def delete_me(
    user: dict = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    if not settings.supabase_service_role_key:
        raise HTTPException(status_code=500, detail="admin key not configured")
    url = settings.supabase_url.rstrip("/") + f"/auth/v1/admin/users/{user['id']}"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.delete(
            url,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="could not delete auth user")
    return {"ok": True}
