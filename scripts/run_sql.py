"""Apply a SQL file against DATABASE_URL using psycopg."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fplcore" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from fplcore.db.connection import _dsn  # noqa: E402
from fplcore.settings import get_settings  # noqa: E402
from sqlutil import split_sql  # noqa: E402


def apply_sql(path: Path, *, autocommit: bool = False) -> None:
    script = path.read_text(encoding="utf-8")
    statements = split_sql(script)
    settings = get_settings()
    with psycopg.connect(_dsn(settings.database_url), autocommit=autocommit) as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        if not autocommit:
            conn.commit()
    print(f"applied {path.name}: {len(statements)} statements")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sql_file")
    parser.add_argument("--autocommit", action="store_true")
    args = parser.parse_args()
    apply_sql(Path(args.sql_file), autocommit=args.autocommit)


if __name__ == "__main__":
    main()
