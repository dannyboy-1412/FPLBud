from pathlib import Path

import pytest
from evals.chat.world.load import assert_safe_url, load_world
from evals.chat.world.sql_split import split_sql
from evals.chat.world.synthetic import SEASON, USER_ID

from fplcore.db import chat_repo
from fplcore.db.stats_repo import fixtures_for

ROOT = Path(__file__).resolve().parents[1]


def test_schema_functions_stay_in_one_statement() -> None:
    statements = split_sql((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    trigger = next(statement for statement in statements if "handle_new_user" in statement)
    assert "raw_user_meta_data" in trigger
    assert len(statements) > 20


def test_world_refuses_hosted_databases() -> None:
    with pytest.raises(RuntimeError):
        assert_safe_url("postgresql://postgres:secret@db.example.supabase.co:5432/postgres")
    with pytest.raises(RuntimeError):
        assert_safe_url("postgresql://postgres:postgres@localhost:5432/fplbud")


@pytest.mark.db
def test_world_loads_a_team_and_an_unscheduled_fixture() -> None:
    url = load_world()
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row) as conn:
        conn.execute("set search_path to fpl, public")
        rows = fixtures_for(conn, SEASON, [9], team=1)
        assert any(row["event"] is None for row in rows)
        assert chat_repo.latest_snapshot(conn, USER_ID) is not None
    load_world(url, variant="blank_gw")
    with psycopg.connect(url, row_factory=dict_row) as conn:
        conn.execute("set search_path to fpl, public")
        blank = fixtures_for(conn, SEASON, [9], team=1)
        scheduled = [row for row in blank if row["event"] == 9]
        assert scheduled == []
