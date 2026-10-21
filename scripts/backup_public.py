"""Dump every non-auth user table as JSON into backups/."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fplcore" / "src"))

from fplcore.db import connect  # noqa: E402

SKIP_SCHEMAS = {
    "auth",
    "pg_catalog",
    "information_schema",
    "pg_toast",
    "extensions",
    "graphql",
    "graphql_public",
    "realtime",
    "vault",
    "pgsodium",
    "pgsodium_masks",
    "net",
    "cron",
    "pgbouncer",
    "supabase_functions",
    "supabase_migrations",
}


def main() -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = ROOT / "backups" / f"old_project_{stamp}"
    dest.mkdir(parents=True, exist_ok=True)

    with connect(autocommit=True) as conn:
        tables = list(
            conn.execute(
                """
                select schemaname, tablename
                from pg_tables
                where schemaname <> all(%s)
                order by 1, 2
                """,
                [list(SKIP_SCHEMAS)],
            )
        )
        users = conn.execute("select count(*) as n from auth.users").fetchone()["n"]
        meta = {"auth_users": users, "tables": tables}
        (dest / "meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        for row in tables:
            schema, table = row["schemaname"], row["tablename"]
            try:
                rows = list(conn.execute(f'select * from "{schema}"."{table}"'))
            except Exception as exc:  # noqa: BLE001
                (dest / f"{schema}.{table}.error.txt").write_text(str(exc), encoding="utf-8")
                continue
            path = dest / f"{schema}.{table}.json"
            path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
            print(f"dumped {schema}.{table}: {len(rows)} rows")
    print(f"backup written to {dest}")
    print(f"auth.users count: {users}")


if __name__ == "__main__":
    main()
