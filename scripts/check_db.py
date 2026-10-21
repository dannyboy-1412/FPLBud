"""Smoke-check the FPLBud schema and report the auth.users count."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fplcore" / "src"))

from fplcore.db import connect  # noqa: E402

EXPECTED_FPL_TABLES = {
    "seasons",
    "teams",
    "positions",
    "gameweeks",
    "fixtures",
    "players",
    "player_daily_snapshots",
    "player_gameweek_stats",
    "player_gw_points",
    "player_metrics",
    "entry_cache",
    "ingest_runs",
    "data_versions",
    "tracked_entries",
    "team_snapshots",
    "agent_runs",
    "agent_suggestions",
    "llm_usage",
}


def main() -> None:
    with connect() as conn:
        fpl_tables = {
            row["tablename"]
            for row in conn.execute(
                "select tablename from pg_tables where schemaname = 'fpl'"
            )
        }
        public_tables = {
            row["tablename"]
            for row in conn.execute(
                "select tablename from pg_tables where schemaname = 'public'"
            )
        }
        user_count = conn.execute("select count(*) as n from auth.users").fetchone()["n"]
        profile_count = 0
        if "profiles" in public_tables:
            profile_count = conn.execute("select count(*) as n from public.profiles").fetchone()["n"]

    missing = EXPECTED_FPL_TABLES - fpl_tables
    print(f"fpl tables: {sorted(fpl_tables)}")
    print(f"public tables: {sorted(public_tables)}")
    print(f"auth.users: {user_count}")
    print(f"public.profiles: {profile_count}")
    if missing:
        print(f"MISSING fpl tables: {sorted(missing)}")
        raise SystemExit(1)
    if "profiles" not in public_tables:
        print("MISSING public.profiles")
        raise SystemExit(1)
    print("ok")


if __name__ == "__main__":
    main()
