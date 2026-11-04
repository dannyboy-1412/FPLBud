"""Chat threads, turns, traces and the daily caps. Callers commit."""

from __future__ import annotations

from typing import Any, cast

from psycopg import Connection
from psycopg.errors import UniqueViolation
from psycopg.types.json import Json

MEMORY_KEYS = frozenset(
    {
        "risk_appetite",
        "favourite_team",
        "avoid_player_ids",
        "prefers_differentials",
        "notes_short",
    }
)
STALE_RUNNING_SECONDS = 120


def _json(value: Any) -> Json | None:
    if value is None:
        return None
    return Json(value)


def _mapped(row: Any) -> dict[str, Any]:
    if row is None:
        raise RuntimeError("expected a database row")
    return cast(dict[str, Any], row)


def _one(conn: Connection, sql: str, params: list[Any]) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return dict(_mapped(row))


def _sid(value: object) -> str:
    return str(value)


def get_thread(conn: Connection, thread_id: str, user_id: str) -> dict[str, Any] | None:
    return _one(
        conn,
        """
        select id, user_id, title, context, context_data_version, summary,
               message_count, created_at, updated_at
          from chat_threads
         where id = %s and user_id = %s and archived_at is null
        """,
        [thread_id, user_id],
    )


def list_threads(conn: Connection, user_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select id, title, message_count, updated_at, created_at
          from chat_threads
         where user_id = %s and archived_at is null
         order by updated_at desc
         limit %s
        """,
        [user_id, limit],
    ).fetchall()
    return [_mapped(row) for row in rows]


def create_thread(conn: Connection, user_id: str, title: str | None = None) -> dict[str, Any]:
    row = conn.execute(
        """
        insert into chat_threads (user_id, title)
        values (%s, %s)
        returning id, title, message_count, created_at, updated_at
        """,
        [user_id, title],
    ).fetchone()
    return _mapped(row)


def delete_thread(conn: Connection, thread_id: str, user_id: str) -> bool:
    cur = conn.execute(
        "delete from chat_threads where id = %s and user_id = %s",
        [thread_id, user_id],
    )
    return cur.rowcount > 0


def delete_all_threads(conn: Connection, user_id: str) -> int:
    cur = conn.execute("delete from chat_threads where user_id = %s", [user_id])
    return int(cur.rowcount)


def pin_context(
    conn: Connection,
    thread_id: str,
    context: dict[str, Any],
    data_version: int | None,
) -> bool:
    """Write the pinned CONTEXT block once. Later turns append an update instead."""
    cur = conn.execute(
        """
        update chat_threads
           set context = %s, context_data_version = %s
         where id = %s and context is null
        """,
        [_json(context), data_version, thread_id],
    )
    return cur.rowcount > 0


def replace_context(
    conn: Connection,
    thread_id: str,
    context: dict[str, Any],
    data_version: int | None,
) -> bool:
    """Replace the pinned block when the published squad has changed."""
    cur = conn.execute(
        """
        update chat_threads
           set context = %s, context_data_version = %s
         where id = %s
        """,
        [_json(context), data_version, thread_id],
    )
    return cur.rowcount > 0


def visible_messages(conn: Connection, thread_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select id, role, content, citations, feedback, created_at, seq
          from chat_messages
         where thread_id = %s
           and role in ('user', 'assistant')
           and tool_calls is null
         order by seq
        """,
        [thread_id],
    ).fetchall()
    return [_mapped(row) for row in rows]


def model_messages(conn: Connection, thread_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select id, role, content, tool_call_id, tool_calls, seq, turn_id
          from chat_messages
         where thread_id = %s
         order by seq
        """,
        [thread_id],
    ).fetchall()
    return [_mapped(row) for row in rows]


def claim_turn(
    conn: Connection,
    *,
    user_id: str,
    thread_id: str,
    text: str,
    client_msg_id: str | None,
    client: str | None,
    prompt_version: str,
    rules_version: str | None,
    data_version: int | None,
    daily_cap: int,
    global_cap_usd: float,
) -> dict[str, Any]:
    """Start a turn, replay a finished one, or refuse.

    A failed turn with the same client_msg_id is retried without spending another
    daily turn. The one-running index is the lock; a clash comes back as busy.
    """
    locked = _one(
        conn,
        """
        select id, title from chat_threads
         where id = %s and user_id = %s and archived_at is null
           for update
        """,
        [thread_id, user_id],
    )
    if locked is None:
        return {"status": "missing"}

    conn.execute(
        """
        update chat_turns
           set status = 'abandoned', finished_at = now(), error_code = 'abandoned'
         where thread_id = %s and status = 'running'
           and started_at < now() - (%s || ' seconds')::interval
        """,
        [thread_id, STALE_RUNNING_SECONDS],
    )

    existing = None
    if client_msg_id:
        existing = _one(
            conn,
            """
            select id, turn_id from chat_messages
             where thread_id = %s and client_msg_id = %s and role = 'user'
            """,
            [thread_id, client_msg_id],
        )
    if existing is not None and existing["turn_id"] is not None:
        prior = _one(conn, "select * from chat_turns where id = %s", [existing["turn_id"]])
        if prior is not None and prior["status"] == "running":
            return {"status": "busy"}
        answer = _final_answer(conn, int(existing["turn_id"]))
        if prior is not None and prior["status"] in {"ok", "fallback"} and answer is not None:
            return {
                "status": "replay",
                "turn_id": int(prior["id"]),
                "message_id": int(answer["id"]),
                "text": answer["content"],
                "citations": answer["citations"] or [],
                "grounding": _grounding(prior),
                "turns_left": turns_remaining(conn, user_id, daily_cap),
            }
        return _open_turn(
            conn,
            user_id=user_id,
            thread_id=thread_id,
            text=text,
            client_msg_id=None,
            client=client,
            prompt_version=prompt_version,
            rules_version=rules_version,
            data_version=data_version,
            daily_cap=daily_cap,
            global_cap_usd=global_cap_usd,
            user_message_id=int(existing["id"]),
            charge=False,
            title_seed=None,
        )

    return _open_turn(
        conn,
        user_id=user_id,
        thread_id=thread_id,
        text=text,
        client_msg_id=client_msg_id,
        client=client,
        prompt_version=prompt_version,
        rules_version=rules_version,
        data_version=data_version,
        daily_cap=daily_cap,
        global_cap_usd=global_cap_usd,
        user_message_id=None,
        charge=True,
        title_seed=text,
    )


def record_blocked(
    conn: Connection,
    *,
    user_id: str,
    thread_id: str,
    text: str,
    client_msg_id: str | None,
    client: str | None,
    prompt_version: str,
    error_code: str,
) -> dict[str, Any] | None:
    """Store a rejected message without spending a daily turn."""
    locked = _one(
        conn,
        """
        select id from chat_threads
         where id = %s and user_id = %s and archived_at is null
           for update
        """,
        [thread_id, user_id],
    )
    if locked is None:
        return None
    conn.execute("savepoint blocked_msg")
    try:
        saved = _insert_blocked(
            conn,
            user_id=user_id,
            thread_id=thread_id,
            text=text,
            client_msg_id=client_msg_id,
            client=client,
            prompt_version=prompt_version,
            error_code=error_code,
        )
        conn.execute("release savepoint blocked_msg")
    except UniqueViolation:
        conn.execute("rollback to savepoint blocked_msg")
        return None
    return saved


def _insert_blocked(
    conn: Connection,
    *,
    user_id: str,
    thread_id: str,
    text: str,
    client_msg_id: str | None,
    client: str | None,
    prompt_version: str,
    error_code: str,
) -> dict[str, Any]:
    turn_id = _insert_turn(
        conn,
        thread_id=thread_id,
        user_id=user_id,
        prompt_version=prompt_version,
        rules_version=None,
        data_version=None,
        client=client,
        user_text_len=len(text),
        status="blocked",
        error_code=error_code,
    )
    message_id = _insert_message(
        conn,
        thread_id=thread_id,
        turn_id=turn_id,
        role="user",
        content=text,
        client_msg_id=client_msg_id,
    )
    conn.execute(
        """
        update chat_threads
           set message_count = message_count + 1,
               updated_at = now(),
               title = coalesce(title, left(%s, 60))
         where id = %s
        """,
        [text, thread_id],
    )
    return {"turn_id": turn_id, "message_id": message_id}


def append_messages(
    conn: Connection,
    thread_id: str,
    turn_id: int,
    rows: list[dict[str, Any]],
) -> list[int]:
    ids: list[int] = []
    for row in rows:
        ids.append(
            _insert_message(
                conn,
                thread_id=thread_id,
                turn_id=turn_id,
                role=str(row["role"]),
                content=str(row.get("content") or ""),
                tool_call_id=row.get("tool_call_id"),
                tool_calls=row.get("tool_calls"),
                citations=row.get("citations"),
            )
        )
    return ids


def record_tool_call(
    conn: Connection,
    *,
    turn_id: int,
    round_no: int,
    name: str,
    args: dict[str, Any] | None,
    ok: bool,
    error_code: str | None,
    result_tokens: int | None,
    result: dict[str, Any] | None,
    duration_ms: int | None,
) -> None:
    conn.execute(
        """
        insert into chat_tool_calls
          (turn_id, round, name, args, ok, error_code, result_tokens, result, duration_ms)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            turn_id,
            round_no,
            name,
            _json(args),
            ok,
            error_code,
            result_tokens,
            _json(result),
            duration_ms,
        ],
    )


def complete_turn(
    conn: Connection,
    *,
    turn_id: int,
    thread_id: str,
    user_id: str,
    text: str,
    citations: list[dict[str, Any]] | None,
    status: str,
    model: str | None,
    rounds: int,
    tool_call_count: int,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
    cost_usd: float | None,
    latency_ms: int | None,
    first_token_ms: int | None,
    grounding_flags: dict[str, Any] | None,
    repaired: bool,
    error_code: str | None,
) -> int:
    message_id = _insert_message(
        conn,
        thread_id=thread_id,
        turn_id=turn_id,
        role="assistant",
        content=text,
        citations=citations,
    )
    conn.execute(
        """
        update chat_turns
           set status = %s, finished_at = now(), model = %s, rounds = %s,
               tool_call_count = %s, input_tokens = %s, output_tokens = %s,
               cached_tokens = %s, cost_usd = %s, latency_ms = %s, first_token_ms = %s,
               grounding_flags = %s, repaired = %s, error_code = %s
         where id = %s
        """,
        [
            status,
            model,
            rounds,
            tool_call_count,
            input_tokens,
            output_tokens,
            cached_tokens,
            cost_usd,
            latency_ms,
            first_token_ms,
            _json(grounding_flags),
            repaired,
            error_code,
            turn_id,
        ],
    )
    conn.execute(
        """
        update chat_threads
           set message_count = message_count + 1, updated_at = now()
         where id = %s
        """,
        [thread_id],
    )
    _add_usage(
        conn,
        user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd or 0,
    )
    _add_global(conn, cost_usd=cost_usd or 0, turns=1)
    return message_id


def abandon_turn(
    conn: Connection,
    turn_id: int,
    *,
    user_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    cost_usd: float | None = None,
) -> bool:
    cur = conn.execute(
        """
        update chat_turns
           set status = 'abandoned', finished_at = now(), error_code = 'abandoned',
               input_tokens = %s, output_tokens = %s, cached_tokens = %s, cost_usd = %s
         where id = %s and status = 'running'
        """,
        [input_tokens, output_tokens, cached_tokens, cost_usd, turn_id],
    )
    if cur.rowcount < 1:
        return False
    _add_usage(
        conn,
        user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd or 0,
    )
    _add_global(conn, cost_usd=cost_usd or 0, turns=0)
    return True


def fail_turn(
    conn: Connection,
    turn_id: int,
    *,
    user_id: str,
    error_code: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float | None = None,
) -> None:
    conn.execute(
        """
        update chat_turns
           set status = 'error', finished_at = now(), error_code = %s,
               input_tokens = %s, output_tokens = %s, cost_usd = %s
         where id = %s and status = 'running'
        """,
        [error_code, input_tokens, output_tokens, cost_usd, turn_id],
    )
    _add_usage(
        conn,
        user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd or 0,
    )
    _add_global(conn, cost_usd=cost_usd or 0, turns=0)


def set_feedback(
    conn: Connection,
    message_id: int,
    user_id: str,
    value: int,
    reason: str | None,
) -> bool:
    cur = conn.execute(
        """
        update chat_messages as m
           set feedback = %s, feedback_reason = %s
          from chat_threads as t
         where m.id = %s and m.thread_id = t.id and t.user_id = %s
           and m.role = 'assistant'
        """,
        [value, reason, message_id, user_id],
    )
    return cur.rowcount > 0


def usage_today(conn: Connection, user_id: str) -> dict[str, Any]:
    row = _one(
        conn,
        """
        select turns, input_tokens, output_tokens, cost_usd, optimiser_calls
          from chat_usage
         where user_id = %s and day = current_date
        """,
        [user_id],
    )
    if row is None:
        return {
            "turns": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "optimiser_calls": 0,
        }
    row["cost_usd"] = float(row["cost_usd"])
    return row


def turns_remaining(conn: Connection, user_id: str, daily_cap: int) -> int:
    used = int(usage_today(conn, user_id)["turns"])
    return max(0, daily_cap - used)


def global_spend(conn: Connection) -> float:
    row = _one(
        conn,
        "select cost_usd from chat_usage_global where day = current_date",
        [],
    )
    if row is None:
        return 0.0
    return float(row["cost_usd"])


def consume_optimiser(conn: Connection, user_id: str, hourly_cap: int) -> bool:
    """Refuse once this user has started `hourly_cap` optimiser calls in the last hour."""
    used = count_optimiser_calls(conn, user_id, within_seconds=3600)
    if used >= hourly_cap:
        return False
    row = conn.execute(
        """
        insert into chat_usage (user_id, day, optimiser_calls)
        values (%s, current_date, 1)
        on conflict (user_id, day) do update
          set optimiser_calls = chat_usage.optimiser_calls + 1
        returning optimiser_calls
        """,
        [user_id],
    ).fetchone()
    return row is not None


def count_optimiser_calls(conn: Connection, user_id: str, *, within_seconds: int) -> int:
    row = conn.execute(
        """
        select count(*) as n
          from chat_tool_calls c
          join chat_turns t on t.id = c.turn_id
         where t.user_id = %s
           and c.name = 'run_transfer_optimiser'
           and c.created_at > now() - (%s || ' seconds')::interval
        """,
        [user_id, within_seconds],
    ).fetchone()
    return int(_mapped(row)["n"]) if row is not None else 0


def list_memory(conn: Connection, user_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select key, value, confirmed_at
          from chat_memory
         where user_id = %s
         order by key
        """,
        [user_id],
    ).fetchall()
    return [_mapped(row) for row in rows]


def delete_memory(conn: Connection, user_id: str, key: str) -> bool:
    cur = conn.execute(
        "delete from chat_memory where user_id = %s and key = %s",
        [user_id, key],
    )
    return cur.rowcount > 0


def delete_all_memory(conn: Connection, user_id: str) -> int:
    cur = conn.execute("delete from chat_memory where user_id = %s", [user_id])
    return int(cur.rowcount)


def propose_memory(
    conn: Connection,
    *,
    user_id: str,
    thread_id: str,
    key: str,
    value: str,
) -> int | None:
    if key not in MEMORY_KEYS:
        return None
    clipped = value.strip()[:80]
    if not clipped:
        return None
    row = conn.execute(
        """
        insert into chat_memory_proposals (user_id, thread_id, key, value)
        values (%s, %s, %s, %s)
        returning id
        """,
        [user_id, thread_id, key, clipped],
    ).fetchone()
    return int(_mapped(row)["id"]) if row is not None else None


def confirm_proposal(conn: Connection, proposal_id: int, user_id: str) -> dict[str, Any] | None:
    row = _one(
        conn,
        """
        select id, key, value
          from chat_memory_proposals
         where id = %s and user_id = %s and status = 'pending'
           and created_at > now() - interval '1 day'
           for update
        """,
        [proposal_id, user_id],
    )
    if row is None or row["key"] not in MEMORY_KEYS:
        if row is not None:
            conn.execute(
                "update chat_memory_proposals set status = 'dismissed' where id = %s",
                [proposal_id],
            )
        return None
    conn.execute(
        """
        insert into chat_memory (user_id, key, value)
        values (%s, %s, %s)
        on conflict (user_id, key) do update
          set value = excluded.value, confirmed_at = now()
        """,
        [user_id, row["key"], row["value"]],
    )
    conn.execute(
        "update chat_memory_proposals set status = 'confirmed' where id = %s",
        [proposal_id],
    )
    return {"key": row["key"], "value": row["value"]}


def dismiss_proposal(conn: Connection, proposal_id: int, user_id: str) -> bool:
    cur = conn.execute(
        """
        update chat_memory_proposals
           set status = 'dismissed'
         where id = %s and user_id = %s and status = 'pending'
        """,
        [proposal_id, user_id],
    )
    return cur.rowcount > 0


def load_turn_trace(conn: Connection, turn_id: int) -> dict[str, Any] | None:
    turn = _one(conn, "select * from chat_turns where id = %s", [turn_id])
    if turn is None:
        return None
    messages = conn.execute(
        """
        select seq, role, content, tool_call_id, tool_calls, citations
          from chat_messages
         where turn_id = %s
         order by seq
        """,
        [turn_id],
    ).fetchall()
    tools = conn.execute(
        """
        select round, name, args, ok, error_code, result_tokens, duration_ms, result
          from chat_tool_calls
         where turn_id = %s
         order by id
        """,
        [turn_id],
    ).fetchall()
    return {
        "turn": turn,
        "messages": [_mapped(row) for row in messages],
        "tool_calls": [_mapped(row) for row in tools],
    }


def latest_snapshot(conn: Connection, user_id: str) -> dict[str, Any] | None:
    return _one(
        conn,
        """
        select id, entry_id, event, season_id, picks, bank, team_value, free_transfers,
               selling_prices, chips_available, chips_used, active_chip, flags,
               overrides, content_hash, fetched_at
          from team_snapshots
         where created_by = %s
         order by fetched_at desc
         limit 1
        """,
        [user_id],
    )


def profile_for_chat(conn: Connection, user_id: str) -> dict[str, Any] | None:
    return _one(
        conn,
        """
        select display_name, fpl_team_name, fpl_entry_id, onboarded_at,
               max_hits, weights, default_horizon
          from public.profiles
         where id = %s
        """,
        [user_id],
    )


def prune_chat(
    conn: Connection,
    *,
    thread_days: int,
    trace_days: int,
    usage_days: int,
    proposal_days: int = 1,
) -> dict[str, int]:
    threads = conn.execute(
        """
        delete from chat_threads
         where updated_at < now() - (%s || ' days')::interval
        """,
        [thread_days],
    )
    traces = conn.execute(
        """
        update chat_tool_calls
           set result = null
         where result is not null
           and created_at < now() - (%s || ' days')::interval
        """,
        [trace_days],
    )
    usage = conn.execute(
        "delete from chat_usage where day < current_date - %s",
        [usage_days],
    )
    global_usage = conn.execute(
        "delete from chat_usage_global where day < current_date - %s",
        [usage_days],
    )
    proposals = conn.execute(
        """
        delete from chat_memory_proposals
         where created_at < now() - (%s || ' days')::interval
        """,
        [proposal_days],
    )
    return {
        "chat_threads": int(threads.rowcount),
        "chat_tool_calls": int(traces.rowcount),
        "chat_usage": int(usage.rowcount),
        "chat_usage_global": int(global_usage.rowcount),
        "chat_memory_proposals": int(proposals.rowcount),
    }


def _open_turn(
    conn: Connection,
    *,
    user_id: str,
    thread_id: str,
    text: str,
    client_msg_id: str | None,
    client: str | None,
    prompt_version: str,
    rules_version: str | None,
    data_version: int | None,
    daily_cap: int,
    global_cap_usd: float,
    user_message_id: int | None,
    charge: bool,
    title_seed: str | None,
) -> dict[str, Any]:
    conn.execute("savepoint claim_turn")
    try:
        if charge and global_spend_locked(conn) >= global_cap_usd:
            _release_claim(conn, rollback=True)
            return {"status": "capped", "scope": "global", "turns_left": 0}
        if charge:
            consumed = _consume_turn(conn, user_id, daily_cap)
            if consumed is None:
                _release_claim(conn, rollback=True)
                return {
                    "status": "capped",
                    "scope": "user",
                    "turns_left": 0,
                }
            turns_left = max(0, daily_cap - consumed)
        else:
            turns_left = turns_remaining(conn, user_id, daily_cap)
        turn_id = _insert_turn(
            conn,
            thread_id=thread_id,
            user_id=user_id,
            prompt_version=prompt_version,
            rules_version=rules_version,
            data_version=data_version,
            client=client,
            user_text_len=len(text),
            status="running",
            error_code=None,
        )
        if user_message_id is None:
            user_message_id = _insert_message(
                conn,
                thread_id=thread_id,
                turn_id=turn_id,
                role="user",
                content=text,
                client_msg_id=client_msg_id,
            )
            conn.execute(
                """
                update chat_threads
                   set message_count = message_count + 1,
                       updated_at = now(),
                       title = coalesce(title, left(%s, 60))
                 where id = %s
                """,
                [title_seed or text, thread_id],
            )
        else:
            conn.execute(
                "update chat_messages set turn_id = %s where id = %s",
                [turn_id, user_message_id],
            )
        conn.execute("release savepoint claim_turn")
    except UniqueViolation:
        conn.execute("rollback to savepoint claim_turn")
        return {"status": "busy"}
    return {
        "status": "start",
        "turn_id": turn_id,
        "user_message_id": user_message_id,
        "turns_left": turns_left,
        "charged": charge,
    }


def _release_claim(conn: Connection, *, rollback: bool) -> None:
    if rollback:
        conn.execute("rollback to savepoint claim_turn")
    conn.execute("release savepoint claim_turn")


def global_spend_locked(conn: Connection) -> float:
    conn.execute(
        """
        insert into chat_usage_global (day, turns, cost_usd)
        values (current_date, 0, 0)
        on conflict (day) do nothing
        """
    )
    row = conn.execute(
        "select cost_usd from chat_usage_global where day = current_date for update",
    ).fetchone()
    if row is None:
        return 0.0
    return float(_mapped(row)["cost_usd"])


def _consume_turn(conn: Connection, user_id: str, daily_cap: int) -> int | None:
    row = conn.execute(
        """
        insert into chat_usage (user_id, day, turns)
        values (%s, current_date, 1)
        on conflict (user_id, day) do update
          set turns = chat_usage.turns + 1
          where chat_usage.turns < %s
        returning turns
        """,
        [user_id, daily_cap],
    ).fetchone()
    if row is None:
        return None
    return int(_mapped(row)["turns"])


def _add_usage(
    conn: Connection,
    user_id: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    conn.execute(
        """
        insert into chat_usage (user_id, day, input_tokens, output_tokens, cost_usd)
        values (%s, current_date, %s, %s, %s)
        on conflict (user_id, day) do update
          set input_tokens = chat_usage.input_tokens + excluded.input_tokens,
              output_tokens = chat_usage.output_tokens + excluded.output_tokens,
              cost_usd = chat_usage.cost_usd + excluded.cost_usd
        """,
        [user_id, input_tokens, output_tokens, cost_usd],
    )


def _add_global(conn: Connection, *, cost_usd: float, turns: int) -> None:
    conn.execute(
        """
        insert into chat_usage_global (day, turns, cost_usd)
        values (current_date, %s, %s)
        on conflict (day) do update
          set turns = chat_usage_global.turns + excluded.turns,
              cost_usd = chat_usage_global.cost_usd + excluded.cost_usd
        """,
        [turns, cost_usd],
    )


def _insert_turn(
    conn: Connection,
    *,
    thread_id: str,
    user_id: str,
    prompt_version: str,
    rules_version: str | None,
    data_version: int | None,
    client: str | None,
    user_text_len: int,
    status: str,
    error_code: str | None,
) -> int:
    row = conn.execute(
        """
        insert into chat_turns
          (thread_id, user_id, status, prompt_version, rules_version, data_version,
           client, user_text_len, error_code, finished_at)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                case when %s = 'running' then null else now() end)
        returning id
        """,
        [
            thread_id,
            user_id,
            status,
            prompt_version,
            rules_version,
            data_version,
            client,
            user_text_len,
            error_code,
            status,
        ],
    ).fetchone()
    return int(_mapped(row)["id"])


def _insert_message(
    conn: Connection,
    *,
    thread_id: str,
    turn_id: int | None,
    role: str,
    content: str,
    tool_call_id: str | None = None,
    tool_calls: Any = None,
    citations: Any = None,
    client_msg_id: str | None = None,
) -> int:
    row = conn.execute(
        """
        insert into chat_messages
          (thread_id, turn_id, seq, role, content, tool_call_id, tool_calls, citations, client_msg_id)
        values (
          %s, %s,
          coalesce((select max(seq) from chat_messages where thread_id = %s), 0) + 1,
          %s, %s, %s, %s, %s, %s
        )
        returning id
        """,
        [
            thread_id,
            turn_id,
            thread_id,
            role,
            content,
            tool_call_id,
            _json(tool_calls),
            _json(citations),
            client_msg_id,
        ],
    ).fetchone()
    return int(_mapped(row)["id"])


def _final_answer(conn: Connection, turn_id: int) -> dict[str, Any] | None:
    return _one(
        conn,
        """
        select id, content, citations
          from chat_messages
         where turn_id = %s and role = 'assistant' and tool_calls is null
         order by seq desc
         limit 1
        """,
        [turn_id],
    )


def _grounding(turn: dict[str, Any]) -> str:
    if turn["status"] == "fallback":
        return "fallback"
    if turn["repaired"]:
        return "repaired"
    return "ok"


def thread_id_str(row: dict[str, Any]) -> str:
    return _sid(row["id"])
