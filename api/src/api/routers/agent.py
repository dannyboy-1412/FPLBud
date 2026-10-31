from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from psycopg import Connection

from api.auth import current_user
from api.deps import db_conn, get_settings_dep
from api.limiter import limiter
from api.worker import kickoff
from fplcore.agent.queue import enqueue_run
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import latest_succeeded_run
from fplcore.settings import Settings

router = APIRouter()


def _pack_run(conn: Connection, run: dict) -> dict:
    suggestions = list(
        conn.execute(
            "select horizon, plan, alternatives, explanation, explanation_source from agent_suggestions where run_id = %s",
            [run["id"]],
        )
    )
    results = {str(row["horizon"]): row["plan"] for row in suggestions}
    return {
        "id": run["id"],
        "status": run["status"],
        "stage": run["stage"],
        "progress": run["progress"],
        "error": run["error"],
        "trigger": run["trigger"],
        "created_at": run["created_at"],
        "finished_at": run["finished_at"],
        "data_version": run["data_version"],
        "results": results or None,
    }


@router.post("/me/agent/rerun", status_code=202)
@limiter.limit("6/hour")
def rerun(
    request: Request,
    background: BackgroundTasks,
    user: dict = Depends(current_user),
    conn: Connection = Depends(db_conn),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    since = datetime.now(UTC) - timedelta(hours=1)
    used = conn.execute(
        """
        select count(*) as n from agent_runs
         where user_id = %s and trigger = 'user_rerun' and created_at > %s
        """,
        [user["id"], since],
    ).fetchone()["n"]
    if used >= settings.agent_rerun_limit_per_hour:
        raise HTTPException(status_code=429, detail="Easy, gaffer. Too many requests. Try again in a minute.")
    profile = conn.execute("select * from public.profiles where id = %s", [user["id"]]).fetchone()
    if not profile or not profile["fpl_entry_id"]:
        raise HTTPException(status_code=400, detail="no team saved")
    snap = conn.execute(
        """
        select id from team_snapshots
         where created_by = %s and entry_id = %s
         order by fetched_at desc limit 1
        """,
        [user["id"], profile["fpl_entry_id"]],
    ).fetchone()
    if snap is None:
        raise HTTPException(status_code=400, detail="import a team first")
    version = conn.execute("select id from data_versions order by id desc limit 1").fetchone()
    run = enqueue_run(
        conn,
        user_id=user["id"],
        entry_id=int(profile["fpl_entry_id"]),
        snapshot_id=int(snap["id"]),
        trigger="user_rerun",
        weights=profile["weights"] or DEFAULT_WEIGHTS,
        data_version=int(version["id"]) if version else None,
    )
    conn.commit()
    background.add_task(kickoff, settings)
    return {"run_id": int(run["id"]), "status": run["status"]}


@router.get("/me/agent/latest")
def latest(user: dict = Depends(current_user), conn: Connection = Depends(db_conn)) -> dict:
    run = latest_succeeded_run(conn, str(user["id"]))
    if run is None:
        raise HTTPException(status_code=404, detail="no edition yet")
    return _pack_run(conn, run)


@router.get("/agent/runs/{run_id}")
def get_run(run_id: int, user: dict = Depends(current_user), conn: Connection = Depends(db_conn)) -> dict:
    run = conn.execute("select * from agent_runs where id = %s", [run_id]).fetchone()
    if run is None or run["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="run not found")
    return _pack_run(conn, run)
