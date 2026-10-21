from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from api.auth import optional_user
from api.deps import db_conn
from api.services import player_detail, ranked_players
from fplcore.constants import DEFAULT_WEIGHTS

router = APIRouter()


@router.get("/players")
def list_players(
    position: int | None = Query(default=None),
    team: int | None = Query(default=None),
    max_cost: int | None = Query(default=None),
    horizon: int = Query(default=1, ge=1, le=6),
    limit: int = Query(default=200, ge=1, le=200),
    user: dict | None = Depends(optional_user),
    conn: Connection = Depends(db_conn),
) -> dict:
    weights = dict(DEFAULT_WEIGHTS)
    if user:
        row = conn.execute(
            "select weights from public.profiles where id = %s", [user["id"]]
        ).fetchone()
        if row:
            weights = dict(row["weights"])
    ranked = ranked_players(
        conn, weights=weights, position=position, team=team, max_cost=max_cost, horizon=horizon
    )
    return {"players": ranked[:limit], "count": len(ranked), "using_defaults": user is None}


@router.get("/players/{player_id}")
def get_player(player_id: int, conn: Connection = Depends(db_conn)) -> dict:
    detail = player_detail(conn, player_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="player not found")
    return detail
