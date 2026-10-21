from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Json

from fplcore.settings import Settings, get_settings


def _weights_hash(weights: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(weights, sort_keys=True).encode()).hexdigest()


def fail_stale_runs(conn: Connection, settings: Settings | None = None) -> int:
    cfg = settings or get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=cfg.agent_job_timeout_seconds)
    rows = conn.execute(
        """
        update agent_runs
           set status = case when attempts >= %s then 'failed' else 'queued' end,
               error = case when attempts >= %s then 'timed out' else error end,
               locked_by = null
         where status = 'running' and started_at < %s
        returning id, status
        """,
        [cfg.agent_max_attempts, cfg.agent_max_attempts, cutoff],
    ).fetchall()
    return len(rows)


def enqueue_run(
    conn: Connection,
    *,
    user_id: UUID,
    entry_id: int,
    snapshot_id: int,
    trigger: str,
    weights: dict[str, Any],
    data_version: int | None,
    priority: int = 0,
) -> dict[str, Any]:
    w_hash = _weights_hash(weights)
    existing = conn.execute(
        """
        select * from agent_runs
         where user_id = %s and entry_id = %s and status in ('queued', 'running')
         order by created_at desc limit 1
        """,
        [user_id, entry_id],
    ).fetchone()
    if existing:
        return existing

    latest = conn.execute(
        """
        select * from agent_runs
         where user_id = %s and entry_id = %s and status = 'succeeded'
           and snapshot_id = %s and weights_hash = %s
           and data_version is not distinct from %s
         order by finished_at desc nulls last limit 1
        """,
        [user_id, entry_id, snapshot_id, w_hash, data_version],
    ).fetchone()
    if latest and trigger == "import":
        return latest

    return conn.execute(
        """
        insert into agent_runs
            (user_id, entry_id, snapshot_id, trigger, priority, status, weights, weights_hash, data_version)
        values (%s, %s, %s, %s, %s, 'queued', %s, %s, %s)
        returning *
        """,
        [user_id, entry_id, snapshot_id, trigger, priority, Json(weights), w_hash, data_version],
    ).fetchone()


def claim_run(conn: Connection, worker_id: str) -> dict[str, Any] | None:
    fail_stale_runs(conn)
    return conn.execute(
        """
        update agent_runs
           set status = 'running',
               started_at = now(),
               attempts = attempts + 1,
               locked_by = %s
         where id = (
            select id from agent_runs
             where status = 'queued'
             order by priority, created_at
             for update skip locked
             limit 1
         )
        returning *
        """,
        [worker_id],
    ).fetchone()


def update_progress(conn: Connection, run_id: int, *, stage: str, progress: int) -> None:
    conn.execute(
        "update agent_runs set stage = %s, progress = %s where id = %s",
        [stage, progress, run_id],
    )


def finish_run(conn: Connection, run_id: int, *, ok: bool, error: str | None = None) -> None:
    conn.execute(
        """
        update agent_runs
           set status = %s, finished_at = now(), error = %s, locked_by = null, progress = case when %s then 100 else progress end
         where id = %s
        """,
        ["succeeded" if ok else "failed", error, ok, run_id],
    )
