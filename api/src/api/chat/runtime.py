"""One turn: claim, stream, validate, persist. The database connection is never held across a model call."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from psycopg_pool import ConnectionPool

from api.chat.context import build_context
from api.chat.history import prompt_messages, rows_for_round
from api.services import refresh_published_squad
from api.chat.tools import build_registry
from fplcore import constants
from fplcore.chat.events import (
    ChatEvent,
    Citation,
    DoneEvent,
    ErrorEvent,
    MemoryProposalEvent,
    MessageFinal,
    ToolUse,
    TurnStart,
    UsageEvent,
)
from fplcore.chat.guard import GroundingFinaliser, input_check, sanitise_text
from fplcore.chat.loop import LoopFailed, LoopFinished, run_turn
from fplcore.chat.model import OpenAICompatClient
from fplcore.chat.prompt import PROMPT_VERSION, RULES_VERSION
from fplcore.chat.registry import ToolRegistry
from fplcore.chat.types import ChatCfg, Message, ToolContext, Usage
from fplcore.db import chat_repo, pooled_connection
from fplcore.settings import Settings

logger = logging.getLogger("fplbud.chat")

OpenConn = Callable[[], AbstractContextManager[Any]]
BREAKER_WINDOW = 20
BREAKER_ERROR_RATE = 0.30
BREAKER_OPEN_SECONDS = 300


@dataclass
class Refuse:
    status_code: int
    code: str
    message: str
    turns_left: int | None = None
    retryable: bool = False


@dataclass
class Prepared:
    kind: str
    thread_id: str
    user_id: str
    turn_id: int
    user_message_id: int
    turns_left: int
    text: str = ""
    messages: list[Message] = field(default_factory=list)
    view: Any = None
    replay_text: str = ""
    citations: list[Any] = field(default_factory=list)
    tools_used: list[dict[str, str]] = field(default_factory=list)
    grounding: str = "ok"
    message_id: int = 0
    data_as_of: str | None = None


@dataclass
class Breaker:
    outcomes: deque[bool] = field(default_factory=lambda: deque(maxlen=BREAKER_WINDOW))
    open_until: float = 0.0
    alerted: set[str] = field(default_factory=set)

    def allow(self) -> bool:
        return time.monotonic() >= self.open_until

    def record(self, ok: bool) -> None:
        self.outcomes.append(ok)
        if len(self.outcomes) < BREAKER_WINDOW:
            return
        errors = sum(1 for outcome in self.outcomes if not outcome)
        if errors / len(self.outcomes) > BREAKER_ERROR_RATE:
            self.open_until = time.monotonic() + BREAKER_OPEN_SECONDS
            self.outcomes.clear()
            _alert("Chat circuit breaker opened for 5 minutes")


class ChatRuntime:
    def __init__(
        self,
        *,
        settings: Settings,
        open_conn: OpenConn,
        llm: Any,
        tools: ToolRegistry,
        finaliser: Any | None = None,
        canary: str = "",
    ) -> None:
        self.settings = settings
        self.open_conn = open_conn
        self.llm = llm
        self.tools = tools
        self.finaliser = finaliser or GroundingFinaliser()
        self.canary = canary or hashlib.sha256(b"fplbud-chat").hexdigest()[:16]
        self.cfg = cfg_from(settings)
        self._slots = asyncio.Semaphore(max(settings.chat_max_concurrent_turns, 1))
        self.breaker = Breaker()

    def enabled_for(self, user_id: str) -> bool:
        if not constants.CHAT_ENABLED:
            return False
        allowed = self.settings.chat_allowed_ids
        return not allowed or user_id in allowed

    async def acquire(self) -> bool:
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=2)
        except TimeoutError:
            return False
        return True

    def release(self) -> None:
        self._slots.release()

    async def aclose(self) -> None:
        close = getattr(self.llm, "aclose", None)
        if close is not None:
            await close()

    async def prepare(
        self,
        *,
        user_id: str,
        thread_id: str,
        text: str,
        client_msg_id: str | None,
        client: str | None,
    ) -> Prepared | Refuse:
        if not self.breaker.allow():
            return Refuse(503, "UNAVAILABLE", "Chat is paused for a few minutes. Try again shortly.", retryable=True)
        checked = input_check(text, max_chars=self.settings.chat_max_input_chars)
        if not checked.ok:
            await asyncio.to_thread(
                self._block, user_id, thread_id, text[:500], client_msg_id, client, checked.code or "INPUT"
            )
            return Refuse(400, checked.code or "INPUT", checked.message)
        clean, suspected = sanitise_text(checked.text, limit=self.settings.chat_max_input_chars)
        if suspected:
            logger.warning("chat injection suspected user=%s", _hash(user_id, self.settings))
        if not clean:
            return Refuse(400, "EMPTY", "Ask a question about your FPL team.")
        await self._refresh_squad(user_id)
        return await asyncio.to_thread(
            self._prepare_sync,
            user_id,
            thread_id,
            clean,
            client_msg_id,
            client,
        )

    async def _refresh_squad(self, user_id: str) -> None:
        try:
            with self.open_conn() as conn:
                await refresh_published_squad(conn, self.settings, user_id)
        except Exception:
            logger.exception("published squad refresh failed")

    def _block(
        self,
        user_id: str,
        thread_id: str,
        text: str,
        client_msg_id: str | None,
        client: str | None,
        code: str,
    ) -> None:
        with self.open_conn() as conn:
            chat_repo.record_blocked(
                conn,
                user_id=user_id,
                thread_id=thread_id,
                text=text,
                client_msg_id=client_msg_id,
                client=client,
                prompt_version=PROMPT_VERSION,
                error_code=code,
            )

    def _prepare_sync(
        self,
        user_id: str,
        thread_id: str,
        text: str,
        client_msg_id: str | None,
        client: str | None,
    ) -> Prepared | Refuse:
        with self.open_conn() as conn:
            snapshot = chat_repo.latest_snapshot(conn, user_id)
            cap = self.settings.chat_user_turns_per_day if snapshot else self.settings.chat_user_turns_per_day_noteam
            claim = chat_repo.claim_turn(
                conn,
                user_id=user_id,
                thread_id=thread_id,
                text=text,
                client_msg_id=client_msg_id,
                client=(client or "")[:40] or None,
                prompt_version=PROMPT_VERSION,
                rules_version=RULES_VERSION,
                data_version=None,
                daily_cap=cap,
                global_cap_usd=self.settings.chat_global_daily_cost_usd,
            )
            status = str(claim["status"])
            if status == "missing":
                return Refuse(404, "NOT_FOUND", "Thread not found.")
            if status == "busy":
                return Refuse(409, "TURN_IN_PROGRESS", "A question is already running in this thread.")
            if status == "capped":
                if claim.get("scope") == "global":
                    return Refuse(503, "GLOBAL_CAP", "Chat is paused until tomorrow.", turns_left=0)
                return Refuse(
                    429,
                    "CAPPED",
                    "You've used today's questions. They reset at 00:00 UTC.",
                    turns_left=0,
                )
            if status == "replay":
                trace = chat_repo.load_turn_trace(conn, int(claim["turn_id"]))
                used = _tools_from_trace(trace)
                return Prepared(
                    kind="replay",
                    thread_id=thread_id,
                    user_id=user_id,
                    turn_id=int(claim["turn_id"]),
                    user_message_id=int(claim.get("user_message_id") or 0),
                    turns_left=int(claim.get("turns_left") or 0),
                    replay_text=str(claim.get("text") or ""),
                    citations=list(claim.get("citations") or []),
                    grounding=str(claim.get("grounding") or "ok"),
                    message_id=int(claim.get("message_id") or 0),
                    tools_used=used,
                )
            thread = chat_repo.get_thread(conn, thread_id, user_id) or {}
            view = build_context(conn, user_id, now=datetime.now(UTC))
            history = chat_repo.model_messages(conn, thread_id)
            stored = thread.get("context") if isinstance(thread.get("context"), dict) else None
            messages, _pinned, to_pin, update = prompt_messages(
                canary=self.canary,
                view=view,
                stored_context=stored,
                history_rows=history,
                history_budget=self.settings.chat_history_token_budget,
            )
            if to_pin is not None:
                write_context = chat_repo.replace_context if stored else chat_repo.pin_context
                write_context(conn, thread_id, to_pin, view.data_version)
            if update:
                chat_repo.append_messages(
                    conn,
                    thread_id,
                    int(claim["turn_id"]),
                    [{"role": "system", "content": update}],
                )
            _stamp_version(conn, int(claim["turn_id"]), view.data_version)
            if not messages or messages[-1].role != "user" or messages[-1].content != text:
                messages.append(Message(role="user", content=text))
            return Prepared(
                kind="start",
                thread_id=thread_id,
                user_id=user_id,
                turn_id=int(claim["turn_id"]),
                user_message_id=int(claim["user_message_id"]),
                turns_left=int(claim.get("turns_left") or 0),
                text=text,
                messages=messages,
                view=view,
                data_as_of=view.data_as_of,
            )

    async def events(self, prepared: Prepared) -> AsyncIterator[ChatEvent]:
        if prepared.kind == "replay":
            async for event in _replay(prepared):
                yield event
            return
        started = time.perf_counter()
        first_token: int | None = None
        meter = Usage()
        finished = False
        outcome: LoopFinished | None = None
        failed: LoopFailed | None = None
        try:
            yield TurnStart(
                turn_id=prepared.turn_id,
                thread_id=prepared.thread_id,
                user_message_id=prepared.user_message_id,
                prompt_version=PROMPT_VERSION,
                model=self.cfg.model,
            )
            ctx = _tool_context(prepared, self.settings)
            proposals: list[MemoryProposalEvent] = []

            async def on_round(assistant: Message, tool_messages: list[Message]) -> None:
                proposals.extend(_memory_proposals(assistant, tool_messages))
                await self._persist_round(prepared, assistant, tool_messages)

            async for item in run_turn(
                prepared.messages,
                llm=_Meter(self.llm, meter),
                tools=self.tools,
                cfg=self.cfg,
                ctx=ctx,
                context=prepared.view,
                finaliser=self.finaliser,
                on_round=on_round,
                turn_id=prepared.turn_id,
                canary=self.canary,
                prompt_text=prepared.messages[0].content if prepared.messages else "",
            ):
                if isinstance(item, LoopFinished):
                    outcome = item
                    break
                if isinstance(item, LoopFailed):
                    failed = item
                    break
                if first_token is None and getattr(item, "text", None):
                    first_token = int((time.perf_counter() - started) * 1000)
                yield item
            if failed is not None:
                self.breaker.record(False)
                await asyncio.to_thread(self._fail, prepared, failed, meter)
                yield ErrorEvent(
                    code=failed.code,
                    message=failed.message,
                    retryable=failed.retryable,
                    turns_left_today=prepared.turns_left,
                )
                yield DoneEvent(turn_id=prepared.turn_id, status="error")
                return
            if outcome is None:
                failed = LoopFailed("UNAVAILABLE", "Chat is unavailable right now.", True, meter)
                self.breaker.record(False)
                await asyncio.to_thread(self._fail, prepared, failed, meter)
                yield ErrorEvent(code="UNAVAILABLE", message=failed.message, retryable=True, turns_left_today=prepared.turns_left)
                yield DoneEvent(turn_id=prepared.turn_id, status="error")
                return
            self.breaker.record(True)
            message_id = await asyncio.to_thread(
                self._complete, prepared, outcome, meter, started, first_token
            )
            finished = True
            await asyncio.to_thread(_note_spend, self, prepared.user_id)
            yield MessageFinal(
                message_id=message_id,
                text=outcome.text,
                citations=_citations(outcome.citations),
                data_as_of=outcome.data_as_of,
                tools_used=[ToolUse(name=item["name"], args_brief=item["args_brief"]) for item in outcome.tools_used],
                grounding=outcome.grounding,
                disclaimers=list(outcome.disclaimers),
            )
            for proposal in proposals:
                yield proposal
            yield UsageEvent(turns_left_today=prepared.turns_left, tokens=_tokens(outcome.usage))
            yield DoneEvent(turn_id=prepared.turn_id, status="fallback" if outcome.grounding == "fallback" else "ok")
        except (asyncio.CancelledError, GeneratorExit):
            if not finished:
                await asyncio.to_thread(self._abandon, prepared, meter)
            raise
        finally:
            logger.info(
                "chat turn user=%s turn=%s status=%s in=%s out=%s",
                _hash(prepared.user_id, self.settings),
                prepared.turn_id,
                "ok" if finished else "incomplete",
                meter.input_tokens,
                meter.output_tokens,
            )

    async def _persist_round(self, prepared: Prepared, assistant: Message, tool_messages: list[Message]) -> None:
        def write() -> None:
            with self.open_conn() as conn:
                chat_repo.append_messages(
                    conn, prepared.thread_id, prepared.turn_id, rows_for_round(assistant, tool_messages)
                )

        await asyncio.to_thread(write)

    def _complete(
        self,
        prepared: Prepared,
        outcome: LoopFinished,
        meter: Usage,
        started: float,
        first_token: int | None,
    ) -> int:
        usage = outcome.usage
        cost = _cost(usage, self.settings)
        status = "fallback" if outcome.grounding == "fallback" else "ok"
        with self.open_conn() as conn:
            return chat_repo.complete_turn(
                conn,
                turn_id=prepared.turn_id,
                thread_id=prepared.thread_id,
                user_id=prepared.user_id,
                text=outcome.text,
                citations=[item.model_dump(mode="json") for item in _citations(outcome.citations)],
                status=status,
                model=self.cfg.model,
                rounds=outcome.rounds,
                tool_call_count=outcome.tool_call_count,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cached_tokens=usage.cached_tokens,
                cost_usd=cost,
                latency_ms=int((time.perf_counter() - started) * 1000),
                first_token_ms=first_token,
                grounding_flags={"flags": outcome.flags} if outcome.flags else None,
                repaired=outcome.repaired,
                error_code=outcome.error_code,
            )

    def _fail(self, prepared: Prepared, failed: LoopFailed, meter: Usage) -> None:
        del meter
        with self.open_conn() as conn:
            chat_repo.fail_turn(
                conn,
                prepared.turn_id,
                user_id=prepared.user_id,
                error_code=failed.code,
                input_tokens=failed.usage.input_tokens,
                output_tokens=failed.usage.output_tokens,
                cost_usd=_cost(failed.usage, self.settings),
            )

    def _abandon(self, prepared: Prepared, meter: Usage) -> None:
        with self.open_conn() as conn:
            chat_repo.abandon_turn(
                conn,
                prepared.turn_id,
                user_id=prepared.user_id,
                input_tokens=meter.input_tokens,
                output_tokens=meter.output_tokens,
                cached_tokens=meter.cached_tokens,
                cost_usd=_cost(meter, self.settings),
            )


class _Meter:
    def __init__(self, inner: Any, usage: Usage) -> None:
        self.inner = inner
        self.usage = usage

    async def stream(self, messages: list[Message], **kwargs: Any) -> Any:
        turn = await self.inner.stream(messages, **kwargs)
        self.usage.add(turn.usage)
        return turn


def cfg_from(settings: Settings) -> ChatCfg:
    return ChatCfg(
        max_rounds=settings.chat_max_tool_rounds,
        max_tool_calls=settings.chat_max_tool_calls,
        turn_timeout_s=settings.chat_turn_timeout_seconds,
        max_output_tokens=settings.chat_max_output_tokens,
        turn_input_token_cap=settings.chat_turn_input_token_cap,
        max_input_chars=settings.chat_max_input_chars,
        history_token_budget=settings.chat_history_token_budget,
        tool_result_token_cap=settings.chat_tool_result_token_cap,
        tool_result_hard_cap=max(settings.chat_tool_result_token_cap * 2, 3000),
        model=settings.resolved_chat_model,
        fallback_model=settings.chat_llm_fallback_model,
    )


def build_chat_runtime(settings: Settings, pool: ConnectionPool) -> ChatRuntime:
    opener = committed(pool)
    slots = max(1, settings.db_pool_max_size - 2)
    llm = OpenAICompatClient(
        api_key=settings.resolved_chat_api_key,
        base_url=settings.resolved_chat_base_url,
        model=settings.resolved_chat_model,
        fallback_model=settings.chat_llm_fallback_model,
        timeout=settings.chat_turn_timeout_seconds,
        site_url=settings.next_public_site_url,
    )
    return ChatRuntime(
        settings=settings,
        open_conn=opener,
        llm=llm,
        tools=build_registry(opener, settings, db_slots=slots),
        finaliser=GroundingFinaliser(),
    )


def committed(pool: ConnectionPool) -> OpenConn:
    @contextmanager
    def open_conn() -> Any:
        with pooled_connection(pool) as conn:
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()

    return open_conn


def _stamp_version(conn: Any, turn_id: int, data_version: int | None) -> None:
    conn.execute(
        "update chat_turns set data_version = %s where id = %s",
        [data_version, turn_id],
    )


def _tool_context(prepared: Prepared, settings: Settings) -> ToolContext:
    view = prepared.view
    weights = getattr(view, "weights", None)
    return ToolContext(
        user_id=prepared.user_id,
        entry_id=None,
        season_id=view.season_id or None,
        weights=dict(weights) if isinstance(weights, dict) else {},
        snapshot_id=view.snapshot_id,
        data_version=view.data_version,
        now=datetime.now(UTC),
        has_team=bool(view.has_team),
        max_hits=int(view.max_hits),
        default_horizon=int(view.default_horizon),
        onboarded=bool(view.has_team),
        thread_id=prepared.thread_id,
        optimiser_hourly_cap=settings.chat_user_optimiser_per_hour,
    )


def _memory_proposals(assistant: Message, tool_messages: list[Message]) -> list[MemoryProposalEvent]:
    names = {call.id: call.name for call in assistant.tool_calls}
    found: list[MemoryProposalEvent] = []
    for message in tool_messages:
        if names.get(message.tool_call_id or "") != "save_preference":
            continue
        try:
            payload = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or "proposal_id" not in data:
            continue
        found.append(
            MemoryProposalEvent(
                proposal_id=int(data["proposal_id"]),
                key=str(data.get("key") or ""),
                value=str(data.get("value") or ""),
                label=str(data.get("label") or data.get("key") or "Preference"),
            )
        )
    return found


def _citations(items: list[Any]) -> list[Citation]:
    parsed: list[Citation] = []
    for item in items:
        if isinstance(item, Citation):
            parsed.append(item)
        elif isinstance(item, dict) and "player_id" in item:
            parsed.append(Citation.model_validate(item))
    return parsed


def _tokens(usage: Usage) -> dict[str, int]:
    return {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cached": usage.cached_tokens,
    }


def _cost(usage: Usage, settings: Settings) -> float | None:
    if usage.cost_usd is not None:
        return usage.cost_usd
    price_in = settings.chat_price_input_per_mtok
    price_out = settings.chat_price_output_per_mtok
    if price_in is None or price_out is None:
        return None
    cached = usage.cached_tokens
    fresh = max(0, usage.input_tokens - cached)
    cached_price = settings.chat_price_cached_per_mtok or 0
    return (fresh * price_in + cached * cached_price + usage.output_tokens * price_out) / 1_000_000


def _tools_from_trace(trace: dict[str, Any] | None) -> list[dict[str, str]]:
    if not trace:
        return []
    used: list[dict[str, str]] = []
    for row in trace.get("tool_calls") or []:
        brief = str(row.get("args") or "")
        used.append({"name": str(row.get("name") or ""), "args_brief": brief[:120]})
    return used


def _hash(user_id: str, settings: Settings) -> str:
    salt = settings.internal_api_secret or "fplbud"
    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:16]


def _alert(message: str) -> None:
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message)
    except Exception:
        logger.warning("%s", message)


def _note_spend(runtime: ChatRuntime, user_id: str) -> None:
    try:
        with runtime.open_conn() as conn:
            spent = chat_repo.global_spend(conn)
    except Exception:
        logger.exception("chat spend check failed")
        return
    cap = runtime.settings.chat_global_daily_cost_usd
    if cap <= 0:
        return
    ratio = spent / cap
    day = datetime.now(UTC).date().isoformat()
    for mark, label in ((1.0, "100"), (0.8, "80"), (0.5, "50")):
        if ratio + 1e-9 < mark:
            continue
        key = f"{day}:{label}"
        if key in runtime.breaker.alerted:
            break
        runtime.breaker.alerted.add(key)
        _alert(f"Chat daily spend reached {label}% of the cap")
        break


async def _replay(prepared: Prepared) -> AsyncIterator[ChatEvent]:
    yield TurnStart(
        turn_id=prepared.turn_id,
        thread_id=prepared.thread_id,
        user_message_id=prepared.user_message_id,
        prompt_version=PROMPT_VERSION,
        model="",
    )
    grounding = prepared.grounding if prepared.grounding in {"ok", "repaired", "fallback"} else "ok"
    yield MessageFinal(
        message_id=prepared.message_id,
        text=prepared.replay_text,
        citations=_citations(prepared.citations),
        tools_used=[ToolUse(name=item["name"], args_brief=item["args_brief"]) for item in prepared.tools_used],
        grounding=grounding,  # type: ignore[arg-type]
    )
    yield UsageEvent(turns_left_today=prepared.turns_left, tokens={"input": 0, "output": 0, "cached": 0})
    yield DoneEvent(turn_id=prepared.turn_id, status="ok" if grounding != "fallback" else "fallback")
    await asyncio.sleep(0)
