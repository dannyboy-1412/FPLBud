from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from api.deps import db_conn, get_settings_dep
from api.services import load_merged_entry, public_team_payload, snapshot_from_cache
from fplcore.client import FplClient, FplNotFoundError
from fplcore.db.repos import current_season_id
from fplcore.settings import Settings

router = APIRouter()


@router.get("/public/team/{entry_id}")
async def public_team(
    entry_id: int,
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    try:
        async with FplClient(settings) as client:
            payload, bootstrap = await load_merged_entry(conn, client, entry_id)
    except FplNotFoundError:
        raise HTTPException(status_code=404, detail="team not found") from None
    season_id = current_season_id(conn)
    snapshot = snapshot_from_cache(payload, bootstrap, season_id)
    team_names = {team.id: team.short_name for team in bootstrap.teams}
    return public_team_payload(conn, snapshot, team_names=team_names)
