"""Write the frozen public world. Live export only when CHAT_EXPORT_LIVE=1 and the URL is not Supabase."""

from __future__ import annotations

import gzip
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEST = ROOT / "evals" / "chat" / "world" / "base"
TABLES = (
    "seasons",
    "teams",
    "positions",
    "gameweeks",
    "fixtures",
    "players",
    "player_metrics",
    "player_gameweek_stats",
    "player_match_points",
    "player_gw_points",
    "player_daily_snapshots",
    "data_versions",
    "ingest_runs",
)


def main() -> None:
    from evals.chat.world.synthetic import manifest, public_rows

    url = os.environ.get("DATABASE_URL", "")
    if os.environ.get("CHAT_EXPORT_LIVE") == "1" and url and "supabase" not in url.lower():
        rows = _live(url)
    else:
        rows = public_rows()
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "manifest.json").write_text(json.dumps(manifest(), indent=2) + "\n", encoding="utf-8")
    for name in TABLES:
        payload = json.dumps(rows[name], default=_encode, separators=(",", ":")).encode()
        (DEST / f"{name}.json.gz").write_bytes(gzip.compress(payload))
    print(f"wrote {len(TABLES)} tables to {DEST}")


def _encode(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value))


def _live(url: str) -> dict[str, list[dict[str, Any]]]:
    import psycopg
    from psycopg.rows import dict_row

    found: dict[str, list[dict[str, Any]]] = {}
    with psycopg.connect(url, row_factory=dict_row) as conn:
        conn.execute("set search_path to fpl, public")
        for name in TABLES:
            found[name] = [dict(row) for row in conn.execute(f"select * from {name}")]
    return found


if __name__ == "__main__":
    main()
