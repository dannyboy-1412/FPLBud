from fastapi import APIRouter, Depends, Request
from psycopg import Connection

from api.deps import db_conn

router = APIRouter()


@router.get("/health")
def health(request: Request, conn: Connection = Depends(db_conn)) -> dict:
    last = conn.execute(
        "select job, finished_at, ok from ingest_runs order by started_at desc limit 1"
    ).fetchone()
    queued = conn.execute(
        "select count(*) as n from agent_runs where status = 'queued'"
    ).fetchone()["n"]
    return {
        "ok": True,
        "last_ingest": dict(last) if last else None,
        "queue_depth": queued,
    }
