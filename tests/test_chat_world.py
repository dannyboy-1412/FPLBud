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
    scrub = next(statement for statement in statements if "scrub_orphaned_chat_tool_calls" in statement)
    assert "set args = null, result = null" in scrub
    migration = split_sql((ROOT / "db" / "migrations" / "013_chat_tool_call_analytics.sql").read_text(encoding="utf-8"))
    assert any("chat_tool_calls_name_created_idx" in statement for statement in migration)
    assert any("scrub_orphaned_chat_tool_calls" in statement for statement in migration)
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


def _plan_indexes(node: dict) -> set[str]:
    found: set[str] = set()
    index_name = node.get("Index Name")
    if isinstance(index_name, str):
        found.add(index_name)
    for child in node.get("Plans") or []:
        if isinstance(child, dict):
            found.update(_plan_indexes(child))
    return found


@pytest.mark.db
def test_tool_call_analytics_survive_pruning_and_use_index() -> None:
    url = load_world()
    import psycopg
    from psycopg.rows import dict_row

    migration = (ROOT / "db" / "migrations" / "013_chat_tool_call_analytics.sql").read_text(encoding="utf-8")
    with psycopg.connect(url, row_factory=dict_row) as conn:
        conn.execute("set search_path to fpl, public")
        for statement in split_sql(migration):
            conn.execute(statement)

        thread = chat_repo.create_thread(conn, USER_ID, "Old thread")
        thread_id = str(thread["id"])
        claim = chat_repo.claim_turn(
            conn,
            user_id=USER_ID,
            thread_id=thread_id,
            text="Who should I buy?",
            client_msg_id=None,
            client="web",
            prompt_version="v1",
            rules_version="v1",
            data_version=1,
            daily_cap=20,
            global_cap_usd=10.0,
        )
        turn_id = int(claim["turn_id"])
        chat_repo.record_tool_call(
            conn,
            turn_id=turn_id,
            user_id=USER_ID,
            thread_id=thread_id,
            model="openai/gpt-6-luna",
            round_no=1,
            name="get_player",
            args={"player_id": 12},
            ok=True,
            error_code=None,
            cached=False,
            result_tokens=40,
            result={"ok": True, "data": {"id": 12}},
            duration_ms=25,
        )
        chat_repo.record_tool_call(
            conn,
            turn_id=turn_id,
            user_id=USER_ID,
            thread_id=thread_id,
            model="openai/gpt-6-luna",
            round_no=1,
            name="get_player",
            args={"player_id": 12},
            ok=True,
            error_code=None,
            cached=True,
            result_tokens=40,
            result={"ok": True, "data": {"id": 12}},
            duration_ms=0,
        )
        chat_repo.record_tool_call(
            conn,
            turn_id=turn_id,
            user_id=USER_ID,
            thread_id=thread_id,
            model="openai/gpt-6-luna",
            round_no=1,
            name="missing_tool",
            args={"foo": "bar"},
            ok=False,
            error_code="UNKNOWN_TOOL",
            cached=False,
            result_tokens=20,
            result={"ok": False},
            duration_ms=0,
        )
        conn.execute(
            "update chat_threads set updated_at = now() - interval '120 days' where id = %s",
            [thread_id],
        )
        pruned = chat_repo.prune_chat(conn, thread_days=90, trace_days=14, usage_days=35)
        assert pruned["chat_threads"] == 1
        assert pruned["chat_tool_calls_scrubbed"] == 3

        rows = conn.execute(
            """
            select turn_id, user_id, thread_id, model, name, args, ok, error_code, cached, result, duration_ms
              from fpl.chat_tool_calls
             order by id
            """
        ).fetchall()
        assert len(rows) == 3
        for row in rows:
            assert row["turn_id"] is None
            assert str(row["user_id"]) == USER_ID
            assert str(row["thread_id"]) == thread_id
            assert row["model"] == "openai/gpt-6-luna"
            assert row["args"] is None
            assert row["result"] is None
        assert [row["cached"] for row in rows] == [False, True, False]
        assert rows[2]["error_code"] == "UNKNOWN_TOOL"

        weekly = conn.execute(
            """
            select name, count(*) as n
              from fpl.chat_tool_calls
             where created_at > now() - interval '7 days'
             group by name
             order by name
            """
        ).fetchall()
        assert [(row["name"], int(row["n"])) for row in weekly] == [
            ("get_player", 2),
            ("missing_tool", 1),
        ]

        season = conn.execute(
            "select name, count(*) as n from fpl.chat_tool_calls group by name order by name"
        ).fetchall()
        assert [(row["name"], int(row["n"])) for row in season] == [
            ("get_player", 2),
            ("missing_tool", 1),
        ]

        # Manual thread deletion also scrubs raw args/result via trigger.
        live = chat_repo.create_thread(conn, USER_ID, "Live thread")
        live_id = str(live["id"])
        live_claim = chat_repo.claim_turn(
            conn,
            user_id=USER_ID,
            thread_id=live_id,
            text="Hi",
            client_msg_id=None,
            client="web",
            prompt_version="v1",
            rules_version="v1",
            data_version=1,
            daily_cap=20,
            global_cap_usd=10.0,
        )
        chat_repo.record_tool_call(
            conn,
            turn_id=int(live_claim["turn_id"]),
            user_id=USER_ID,
            thread_id=live_id,
            model="openai/gpt-6-luna",
            round_no=1,
            name="get_my_team",
            args={"secret": "user_input"},
            ok=True,
            error_code=None,
            cached=False,
            result_tokens=10,
            result={"ok": True},
            duration_ms=5,
        )
        assert chat_repo.delete_thread(conn, live_id, USER_ID) is True
        manual = conn.execute(
            "select turn_id, args, result from fpl.chat_tool_calls where name = 'get_my_team'"
        ).fetchone()
        assert manual is not None
        assert manual["turn_id"] is None
        assert manual["args"] is None
        assert manual["result"] is None

        conn.execute("set local enable_seqscan = off")
        explained = conn.execute(
            """
            explain (format json)
            select name, count(*)
              from fpl.chat_tool_calls
             where created_at > now() - interval '7 days'
             group by name
            """
        ).fetchone()
        assert explained is not None
        plan = explained["QUERY PLAN"][0]["Plan"]
        used_indexes = _plan_indexes(plan)
        assert used_indexes & {"chat_tool_calls_created_name_idx", "chat_tool_calls_name_created_idx"}
