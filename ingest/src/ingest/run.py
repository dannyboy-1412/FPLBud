from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import UTC, datetime

import pandas as pd

from fplcore.agent.queue import claim_run, enqueue_run
from fplcore.agent.runner import run_claimed
from fplcore.client import FplClient
from fplcore.db import connect
from fplcore.db.repos import (
    current_season_id,
    log_ingest_finish,
    log_ingest_start,
    maybe_daily_snapshots,
    minutes_by_player,
    prune_retention,
    replace_metrics,
    upsert_bootstrap,
    upsert_element_history,
    upsert_fixtures,
)
from fplcore.metrics.compute import compute_player_metrics
from fplcore.settings import get_settings
from ingest.schedule import deadline_is_soon, is_lock_morning

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest")


async def job_bootstrap() -> str:
    settings = get_settings()
    with connect(settings) as conn:
        run_id = log_ingest_start(conn, "bootstrap")
        conn.commit()
        try:
            async with FplClient(settings) as client:
                bootstrap = await client.bootstrap_static()
            sid = upsert_bootstrap(conn, bootstrap)
            maybe_daily_snapshots(conn, bootstrap, sid)
            log_ingest_finish(conn, run_id, ok=True, detail=f"season={sid} players={len(bootstrap.elements)}")
            conn.commit()
            return sid
        except Exception as exc:
            conn.rollback()
            log_ingest_finish(conn, run_id, ok=False, detail=str(exc))
            conn.commit()
            raise


async def job_fixtures() -> None:
    settings = get_settings()
    with connect(settings) as conn:
        run_id = log_ingest_start(conn, "fixtures")
        conn.commit()
        try:
            sid = current_season_id(conn)
            async with FplClient(settings) as client:
                fixtures = await client.fixtures()
            upsert_fixtures(conn, fixtures, sid)
            log_ingest_finish(conn, run_id, ok=True, detail=f"n={len(fixtures)}")
            conn.commit()
        except Exception as exc:
            conn.rollback()
            log_ingest_finish(conn, run_id, ok=False, detail=str(exc))
            conn.commit()
            raise


async def job_element_summaries() -> None:
    settings = get_settings()
    with connect(settings) as conn:
        run_id = log_ingest_start(conn, "element_summaries")
        conn.commit()
        try:
            sid = current_season_id(conn)
            previous = minutes_by_player(conn, sid)
            async with FplClient(settings) as client:
                bootstrap = await client.bootstrap_static()
                upsert_bootstrap(conn, bootstrap)
                conn.commit()
                to_fetch = [
                    el.id
                    for el in bootstrap.elements
                    if previous.get(el.id) != el.minutes or el.id not in previous
                ]
                log.info("element-summary fetches: %s", len(to_fetch))
                for player_id in to_fetch:
                    summary = await client.element_summary(player_id)
                    upsert_element_history(conn, sid, player_id, summary)
            log_ingest_finish(conn, run_id, ok=True, detail=f"fetched={len(to_fetch)}")
            conn.commit()
        except Exception as exc:
            conn.rollback()
            log_ingest_finish(conn, run_id, ok=False, detail=str(exc))
            conn.commit()
            raise


async def job_metrics() -> int:
    settings = get_settings()
    with connect(settings) as conn:
        run_id = log_ingest_start(conn, "metrics")
        conn.commit()
        try:
            sid = current_season_id(conn)
            players = pd.DataFrame(conn.execute("select * from players where season_id = %s", [sid]).fetchall())
            if players.empty:
                raise RuntimeError("no players — run bootstrap first")
            history = pd.DataFrame(
                conn.execute("select * from player_gameweek_stats where season_id = %s", [sid]).fetchall()
            )
            if history.empty:
                history = pd.DataFrame(
                    columns=[
                        "player_id", "round", "minutes", "starts", "total_points",
                        "expected_goals", "expected_assists", "expected_goals_conceded",
                    ]
                )
            fixtures = pd.DataFrame(conn.execute("select * from fixtures where season_id = %s", [sid]).fetchall())
            snapshots = pd.DataFrame(
                conn.execute("select * from player_daily_snapshots where season_id = %s", [sid]).fetchall()
            )
            next_row = conn.execute(
                "select id, deadline_time from gameweeks where season_id = %s and is_next = true", [sid]
            ).fetchone()
            if next_row is None:
                next_row = conn.execute(
                    "select id, deadline_time from gameweeks where season_id = %s order by id desc limit 1", [sid]
                ).fetchone()
            next_gw = int(next_row["id"])
            last_rounds = list(range(max(1, next_gw - 5), next_gw))
            total_players = int(
                conn.execute("select count(*) as n from players where season_id = %s", [sid]).fetchone()["n"]
            )
            prev = conn.execute(
                "select deadline_time from gameweeks where season_id = %s and id = %s",
                [sid, next_gw - 1],
            ).fetchone()
            if prev:
                hours = max(
                    (datetime.now(UTC) - prev["deadline_time"].astimezone(UTC)).total_seconds() / 3600,
                    1.0,
                )
            else:
                hours = 24.0
            if "expected_goals_per_90" not in players.columns:
                mins = players["minutes"].clip(lower=1)
                players["expected_goals_per_90"] = players["expected_goals"] * 90 / mins
                players["expected_assists_per_90"] = players["expected_assists"] * 90 / mins
                players["expected_goals_conceded_per_90"] = players["expected_goals_conceded"] * 90 / mins
            rows = compute_player_metrics(
                players=players,
                history=history,
                fixtures=fixtures,
                snapshots=snapshots,
                next_gw=next_gw,
                last_rounds=last_rounds,
                total_players=total_players,
                hours_since_deadline=hours,
            )
            version = replace_metrics(conn, sid, rows)
            log_ingest_finish(conn, run_id, ok=True, detail=f"version={version} rows={len(rows)}")
            conn.commit()
            return version
        except Exception as exc:
            conn.rollback()
            log_ingest_finish(conn, run_id, ok=False, detail=str(exc))
            conn.commit()
            raise


async def drain_queue(limit: int = 50) -> int:
    settings = get_settings()
    worker = f"gha-{os.getenv('GITHUB_RUN_ID', 'local')}"
    processed = 0
    with connect(settings) as conn:
        while processed < limit:
            run = claim_run(conn, worker)
            conn.commit()
            if run is None:
                break
            await run_claimed(conn, run, settings=settings, worker_id=worker)
            processed += 1
    return processed


async def job_prices() -> None:
    """Daily run after the 00:00 UK price change. One fixtures fetch rides along."""
    await job_bootstrap()
    await job_fixtures()
    await job_metrics()


async def job_lock(*, only_if_due: bool = False) -> None:
    """Full refresh on the morning FPL locks the gameweek, then plans are rebuilt.

    On other mornings this same slot refreshes flags when a deadline is inside
    48 hours, so a midweek deadline is covered without a separate cron.
    """
    if only_if_due and not _lock_is_due():
        if _deadline_is_due():
            log.info("deadline inside 48h; running the pre-deadline ingest")
            await job_pre_deadline()
            return
        log.info("not the morning after a gameweek's last match; skipping lock ingest")
        return
    await job_bootstrap()
    await job_fixtures()
    await job_element_summaries()
    await job_metrics()
    await job_agent_rerun("data_refresh")


async def job_pre_deadline(*, only_if_due: bool = False) -> None:
    """Injury flags in the 48 hours before a deadline, then a plan rebuild."""
    if only_if_due and not _deadline_is_due():
        log.info("next deadline is more than 48h away; skipping pre-deadline ingest")
        return
    await job_bootstrap()
    await job_metrics()
    await job_agent_rerun("pre_deadline")


def _lock_is_due(now: datetime | None = None) -> bool:
    moment = now or datetime.now(UTC)
    with connect() as conn:
        try:
            season_id = current_season_id(conn)
        except RuntimeError:
            return False
        rows = conn.execute(
            """
            select max(kickoff_time) as last_ko
              from fixtures
             where season_id = %s
               and event is not null
               and kickoff_time is not null
             group by event
            """,
            [season_id],
        ).fetchall()
    kickoffs = [row["last_ko"] for row in rows if row["last_ko"] is not None]
    return is_lock_morning(kickoffs, moment)


def _deadline_is_due(now: datetime | None = None) -> bool:
    moment = now or datetime.now(UTC)
    with connect() as conn:
        try:
            season_id = current_season_id(conn)
        except RuntimeError:
            return False
        row = conn.execute(
            """
            select deadline_time
              from gameweeks
             where season_id = %s
               and deadline_time > %s
             order by deadline_time
             limit 1
            """,
            [season_id, moment],
        ).fetchone()
    deadline = row["deadline_time"] if row else None
    return deadline_is_soon(deadline, moment)


async def job_agent_rerun(trigger: str = "data_refresh") -> int:
    settings = get_settings()
    with connect(settings) as conn:
        version_row = conn.execute("select id from data_versions order by id desc limit 1").fetchone()
        data_version = int(version_row["id"]) if version_row else None
        users = list(
            conn.execute(
                """
                select p.id as user_id, te.entry_id, p.weights,
                       (select id from team_snapshots ts
                         where ts.entry_id = te.entry_id and ts.created_by = te.user_id
                         order by fetched_at desc limit 1) as snapshot_id
                  from public.profiles p
                  join tracked_entries te on te.user_id = p.id
                 where p.fpl_entry_id is not null
                   and p.last_active_at > now() - (%s || ' days')::interval
                """,
                [settings.agent_tracking_window_days],
            )
        )
        queued = 0
        for row in users:
            if row["snapshot_id"] is None:
                continue
            enqueue_run(
                conn,
                user_id=row["user_id"],
                entry_id=int(row["entry_id"]),
                snapshot_id=int(row["snapshot_id"]),
                trigger=trigger,
                weights=row["weights"],
                data_version=data_version,
                priority=10,
            )
            queued += 1
        conn.commit()
    drained = await drain_queue()
    log.info("enqueued %s reruns, drained %s", queued, drained)
    _prune()
    return queued


JOBS = {
    "bootstrap": job_bootstrap,
    "fixtures": job_fixtures,
    "element_summaries": job_element_summaries,
    "metrics": job_metrics,
    "agent_rerun": job_agent_rerun,
}


def _prune() -> None:
    with connect() as conn:
        counts = prune_retention(conn)
        conn.commit()
    log.info("pruned %s", counts)


async def run_named(name: str) -> None:
    if name == "all":
        await job_bootstrap()
        await job_fixtures()
        await job_element_summaries()
        await job_metrics()
        _prune()
        return
    if name == "agent_rerun":
        await job_agent_rerun()
        return
    job = JOBS[name]
    await job()
    _prune()


def main() -> None:
    parser = argparse.ArgumentParser(description="FPLBud ingest")
    parser.add_argument("job", choices=[*JOBS, "all", "drain", "prices", "lock", "pre_deadline"])
    parser.add_argument("--trigger", default="data_refresh")
    parser.add_argument(
        "--if-due",
        action="store_true",
        help="For lock and pre_deadline, skip the run when FPL has nothing new to collect",
    )
    args = parser.parse_args()
    if args.job == "drain":
        asyncio.run(drain_queue())
        return
    if args.job == "agent_rerun":
        asyncio.run(job_agent_rerun(args.trigger))
        return
    if args.job == "prices":
        asyncio.run(job_prices())
        _prune()
        return
    if args.job == "lock":
        asyncio.run(job_lock(only_if_due=args.if_due))
        return
    if args.job == "pre_deadline":
        asyncio.run(job_pre_deadline(only_if_due=args.if_due))
        return
    asyncio.run(run_named(args.job))


if __name__ == "__main__":
    main()
