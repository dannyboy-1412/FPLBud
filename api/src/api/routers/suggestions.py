from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg import Connection
from pydantic import BaseModel, Field

from api.auth import optional_user
from api.deps import db_conn, get_settings_dep
from api.limiter import limiter
from api.services import (
    build_horizon_plan,
    load_merged_entry,
    snapshot_from_cache,
)
from fplcore.client import FplClient, FplNotFoundError
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import current_season_id
from fplcore.settings import Settings

router = APIRouter()


class SuggestionBody(BaseModel):
    entry_id: int
    overrides: dict[str, Any] | None = None
    weights: dict[str, float] | None = None
    horizon: int = Field(default=1, ge=1, le=6)
    max_hits: int | None = Field(default=None, ge=0, le=3)
    lock_ids: list[int] = Field(default_factory=list)
    exclude_ids: list[int] = Field(default_factory=list)


@router.post("/suggestions")
@limiter.limit("10/minute")
async def suggestions(
    request: Request,
    body: SuggestionBody,
    user: dict | None = Depends(optional_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    guest = user is None
    horizon = 1 if guest else body.horizon
    weights = dict(DEFAULT_WEIGHTS) if guest else (body.weights or DEFAULT_WEIGHTS)
    try:
        async with FplClient(settings) as client:
            payload, bootstrap = await load_merged_entry(conn, client, body.entry_id)
    except FplNotFoundError:
        raise HTTPException(status_code=404, detail="team not found") from None
    season_id = current_season_id(conn)
    snapshot = snapshot_from_cache(payload, bootstrap, season_id, body.overrides)
    plan = build_horizon_plan(
        conn,
        snapshot,
        weights=weights,
        horizon=horizon,
        max_hits=None if guest else body.max_hits,
        lock_ids=body.lock_ids,
        exclude_ids=body.exclude_ids,
    )
    if plan is None:
        raise HTTPException(status_code=503, detail="metrics not ready")
    return plan
