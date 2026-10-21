"""Read-only inventory of the current Supabase project (non-auth objects)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fplcore" / "src"))

from fplcore.db import connect  # noqa: E402

MANAGED_SCHEMAS = {
    "auth",
    "storage",
    "realtime",
    "extensions",
    "graphql",
    "graphql_public",
    "vault",
    "pgsodium",
    "pgsodium_masks",
    "supabase_functions",
    "supabase_migrations",
    "net",
    "cron",
    "pgbouncer",
    "information_schema",
    "pg_catalog",
    "pg_toast",
}


def main() -> None:
    with connect(autocommit=True) as conn:
        schemas = [
            row["nspname"]
            for row in conn.execute(
                """
                select nspname from pg_namespace
                where nspname not like 'pg_%' and nspname <> 'information_schema'
                order by 1
                """
            )
        ]
        tables = list(
            conn.execute(
                """
                select schemaname, tablename
                from pg_tables
                where schemaname not in ('pg_catalog', 'information_schema')
                order by 1, 2
                """
            )
        )
        views = list(
            conn.execute(
                """
                select schemaname, viewname
                from pg_views
                where schemaname not in ('pg_catalog', 'information_schema')
                order by 1, 2
                """
            )
        )
        functions = list(
            conn.execute(
                """
                select n.nspname as schema, p.proname as name
                from pg_proc p
                join pg_namespace n on n.oid = p.pronamespace
                where n.nspname not in ('pg_catalog', 'information_schema', 'auth',
                                        'extensions', 'graphql', 'graphql_public',
                                        'realtime', 'storage', 'vault', 'pgsodium',
                                        'net', 'cron', 'pgbouncer')
                order by 1, 2
                """
            )
        )
        auth_triggers = list(
            conn.execute(
                """
                select tgname, pg_get_triggerdef(t.oid) as def
                from pg_trigger t
                join pg_class c on c.oid = t.tgrelid
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = 'auth' and c.relname = 'users' and not t.tgisinternal
                """
            )
        )
        buckets = []
        try:
            buckets = list(conn.execute("select id, name, public from storage.buckets"))
        except Exception as exc:  # noqa: BLE001
            buckets = [{"error": str(exc)}]
        cron_jobs = []
        try:
            cron_jobs = list(conn.execute("select jobid, jobname, schedule from cron.job"))
        except Exception:
            cron_jobs = []
        users = conn.execute("select count(*) as n from auth.users").fetchone()["n"]
        identities = conn.execute("select count(*) as n from auth.identities").fetchone()["n"]

    inventory = {
        "schemas": schemas,
        "custom_schemas": [s for s in schemas if s not in MANAGED_SCHEMAS and s != "public"],
        "tables": tables,
        "views": views,
        "functions": functions,
        "auth_user_triggers": auth_triggers,
        "storage_buckets": buckets,
        "cron_jobs": cron_jobs,
        "auth_users": users,
        "auth_identities": identities,
    }
    print(json.dumps(inventory, indent=2, default=str))
    out = ROOT / "backups" / "inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inventory, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
