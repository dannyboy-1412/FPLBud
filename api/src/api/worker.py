from __future__ import annotations

import asyncio
import logging
import os
import time

from fplcore.agent.queue import claim_run
from fplcore.agent.runner import run_claimed
from fplcore.db import pooled_connection
from fplcore.db.repos import prune_retention
from fplcore.settings import Settings

log = logging.getLogger("api.worker")
WORKER_ID = f"api-{os.getpid()}"
PRUNE_INTERVAL_SECONDS = 3600


async def process_one(settings: Settings) -> bool:
    with pooled_connection() as conn:
        run = claim_run(conn, WORKER_ID)
        conn.commit()
        if run is None:
            return False
        await run_claimed(conn, run, settings=settings, worker_id=WORKER_ID)
        return True


def _prune_once() -> None:
    with pooled_connection() as conn:
        counts = prune_retention(conn)
        conn.commit()
    log.info("pruned %s", counts)


async def poll_loop(settings: Settings) -> None:
    log.info("agent worker started as %s", WORKER_ID)
    last_prune = 0.0
    while True:
        try:
            worked = await process_one(settings)
        except Exception:
            log.exception("agent worker failed")
            worked = False
        now = time.monotonic()
        if now - last_prune >= PRUNE_INTERVAL_SECONDS:
            # Stamp the attempt before the query. A failure used to leave
            # last_prune at 0, so a missing chat_threads retried every poll
            # and blocked request handling on this loop.
            last_prune = now
            try:
                await asyncio.to_thread(_prune_once)
            except Exception:
                log.exception("retention prune failed")
        await asyncio.sleep(0 if worked else settings.agent_poll_interval_seconds)


async def _run_kickoff(settings: Settings) -> None:
    try:
        await process_one(settings)
    except Exception:
        log.exception("agent kickoff failed")


async def kickoff(settings: Settings) -> None:
    """Queue one agent pass without blocking the HTTP response.

    FastAPI runs sync background tasks in a worker thread, where
    ``asyncio.create_task`` raises and aborts the response. Scheduling from
    this coroutine keeps the work on the server loop.
    """
    asyncio.create_task(_run_kickoff(settings))
