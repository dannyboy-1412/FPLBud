from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Protocol

from fplcore.chat.events import ChatEvent, MessageDelta, StatusEvent, ToolEnd, ToolStart
from fplcore.chat.guard import Finalised, IdentityFinaliser, fallback_from_results, parse_markup
from fplcore.chat.prompt import FORCE_FINAL_INSTRUCTION, ContextView
from fplcore.chat.registry import ToolRegistry
from fplcore.chat.types import (
    ChatCfg,
    Corpus,
    GroundingState,
    Message,
    ModelTurn,
    ToolCall,
    ToolContext,
    ToolResult,
    TurnCounters,
    Usage,
)

logger = logging.getLogger("fplbud.chat")

INVALID_CODES = {"INVALID_ARGUMENT", "UNKNOWN_TOOL"}


class AnswerFinaliser(Protocol):
    async def finalise(self, draft: str, *, llm: Any, cfg: ChatCfg, corpus: Corpus) -> Finalised: ...


class LlmLike(Protocol):
    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float = 0.2,
        on_text: Callable[[str], None] | None = None,
    ) -> ModelTurn: ...


OnRound = Callable[[Message, list[Message]], Awaitable[None]]


@dataclass
class LoopFinished:
    text: str
    grounding: GroundingState
    citations: list[Any]
    tools_used: list[dict[str, str]]
    data_as_of: str | None
    flags: list[dict[str, str]]
    usage: Usage
    rounds: int
    tool_call_count: int
    repaired: bool
    disclaimers: list[str] = field(default_factory=list)
    error_code: str | None = None


@dataclass
class LoopFailed:
    code: str
    message: str
    retryable: bool
    usage: Usage
    rounds: int = 0
    tool_call_count: int = 0


def tool_label(name: str, arguments: dict[str, Any] | None) -> str:
    labels = {
        "get_gameweek_context": "Checking the deadline",
        "get_my_team": "Reading your squad",
        "search_players": "Searching players",
        "get_player": "Looking up a player",
        "compare_players": "Comparing players",
        "get_fixtures": "Checking fixtures",
        "get_market_movers": "Checking prices",
        "get_insights": "Checking the shortlist",
        "explain_topic": "Checking the rules",
        "get_plan_suggestions": "Reading your saved plan",
        "run_transfer_optimiser": "Running the optimiser",
        "evaluate_transfer": "Checking that transfer",
        "save_preference": "Noting a preference",
    }
    label = labels.get(name, "Looking that up")
    if name == "get_player" and arguments:
        named = arguments.get("name")
        if isinstance(named, str) and named:
            return f"Looking up {named[:40]}"
    return label


def _summary(result: ToolResult) -> str | None:
    if not result.ok or not result.data:
        return None
    for key in ("starters", "players", "results"):
        value = result.data.get(key)
        if isinstance(value, list):
            return f"{len(value)} players"
    return None


def _tools_used(calls: list[tuple[ToolCall, ToolResult]]) -> list[dict[str, str]]:
    used = []
    for call, _result in calls:
        brief = call.canonical_args()
        if len(brief) > 120:
            brief = brief[:117] + "..."
        used.append({"name": call.name, "args_brief": brief})
    return used


def _as_of(results: list[ToolResult], context: ContextView) -> str | None:
    stamps = [result.as_of for result in results if result.as_of]
    if stamps:
        return max(stamps)
    return context.data_as_of


class _Round:
    """Yields text deltas as they arrive, then exposes the finished ModelTurn."""

    def __init__(
        self,
        llm: LlmLike,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None,
        cfg: ChatCfg,
        round_no: int,
        attempt: int,
    ) -> None:
        self.llm = llm
        self.messages = messages
        self.tools = tools
        self.cfg = cfg
        self.round_no = round_no
        self.attempt = attempt
        self.turn: ModelTurn | None = None
        self.error: BaseException | None = None

    async def __aiter__(self) -> AsyncIterator[MessageDelta]:
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async def drive() -> None:
            try:
                turn = await self.llm.stream(
                    self.messages,
                    tools=self.tools,
                    max_tokens=self.cfg.max_output_tokens,
                    temperature=self.cfg.temperature,
                    on_text=lambda text: queue.put_nowait(("text", text)),
                )
                queue.put_nowait(("done", turn))
            except BaseException as exc:
                queue.put_nowait(("err", exc))

        task = asyncio.create_task(drive())
        try:
            while True:
                kind, payload = await queue.get()
                if kind == "text":
                    yield MessageDelta(text=str(payload), round=self.round_no, attempt=self.attempt)
                elif kind == "done":
                    self.turn = payload
                    return
                else:
                    self.error = payload
                    return
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def run_turn(
    messages: list[Message],
    *,
    llm: LlmLike,
    tools: ToolRegistry,
    cfg: ChatCfg,
    ctx: ToolContext,
    context: ContextView,
    finaliser: AnswerFinaliser | None = None,
    on_round: OnRound | None = None,
    turn_id: int | None = None,
    canary: str = "",
    prompt_text: str = "",
) -> AsyncIterator[ChatEvent | LoopFinished | LoopFailed]:
    """One user turn: model calls and tool calls until an answer or a hard limit."""
    checker = finaliser or IdentityFinaliser()
    counters = TurnCounters()
    seen: dict[str, ToolResult] = {}
    ran: list[tuple[ToolCall, ToolResult]] = []
    deadline = monotonic() + cfg.turn_timeout_s
    yield StatusEvent(phase="thinking")
    draft = ""
    failed: LoopFailed | None = None
    while counters.rounds < cfg.max_rounds:
        force = (
            counters.tool_calls >= cfg.max_tool_calls
            or counters.invalid_streak >= 2
            or monotonic() > deadline - 5
            or counters.usage.input_tokens > cfg.turn_input_token_cap
            or counters.rounds == cfg.max_rounds - 1
        )
        call_messages = messages
        if force:
            call_messages = [*messages, Message(role="user", content=FORCE_FINAL_INSTRUCTION)]
        round_no = counters.rounds + 1
        streamed = _Round(
            llm,
            call_messages,
            tools=None if force else tools.specs(),
            cfg=cfg,
            round_no=round_no,
            attempt=1,
        )
        async for delta in streamed:
            yield delta
        if streamed.error is not None:
            from fplcore.chat.model import LlmError

            exc = streamed.error
            logger.warning("chat model call failed: %s", exc)
            retryable = isinstance(exc, LlmError) and exc.retryable
            code = "CAPPED" if isinstance(exc, LlmError) and exc.status == 429 else "UNAVAILABLE"
            if ran and force:
                draft = ""
                break
            failed = LoopFailed(
                code=code,
                message="Chat is unavailable right now. The team agent on the dashboard still works.",
                retryable=retryable,
                usage=counters.usage,
                rounds=counters.rounds,
                tool_call_count=counters.tool_calls,
            )
            break
        turn = streamed.turn
        if turn is None:
            failed = LoopFailed(
                code="UNAVAILABLE",
                message="Chat is unavailable right now. The team agent on the dashboard still works.",
                retryable=True,
                usage=counters.usage,
                rounds=counters.rounds,
                tool_call_count=counters.tool_calls,
            )
            break
        counters.rounds += 1
        counters.usage.add(turn.usage)
        if force or not turn.tool_calls:
            draft = turn.text
            if turn.finish_reason == "length":
                draft = _shorten(draft)
            break
        messages.append(turn.as_assistant_message(turn_index=None))
        yield StatusEvent(phase="tool")
        for call in turn.tool_calls:
            yield ToolStart(call_id=call.id, name=call.name, label=tool_label(call.name, call.arguments))
        results = await asyncio.gather(
            *[
                tools.execute(call, ctx, seen, counters, turn_id=turn_id, round_no=round_no)
                for call in turn.tool_calls
            ]
        )
        tool_messages: list[Message] = []
        invalid = True
        for call, result in zip(turn.tool_calls, results, strict=True):
            ran.append((call, result))
            yield ToolEnd(call_id=call.id, ok=result.ok, ms=result.duration_ms, summary=_summary(result))
            message = Message(
                role="tool",
                content=result.to_model_text(),
                tool_call_id=call.id,
                name=call.name,
            )
            messages.append(message)
            tool_messages.append(message)
            if result.ok or (result.error and result.error.code not in INVALID_CODES):
                invalid = False
        if invalid:
            counters.invalid_streak += 1
        else:
            counters.invalid_streak = 0
        if on_round is not None:
            await on_round(turn.as_assistant_message(), tool_messages)
        yield StatusEvent(phase="thinking")
    if failed is not None:
        yield failed
        return
    corpus = _corpus(
        context,
        ran,
        canary=canary,
        prompt_text=prompt_text,
        user_text=_question_text(messages),
    )
    yield StatusEvent(phase="checking")
    try:
        final = await checker.finalise(draft, llm=llm, cfg=cfg, corpus=corpus)
    except Exception:
        final = Finalised(
            text=corpus.fallback_text,
            grounding="fallback",
            citations=[],
            flags=[{"check": "finaliser", "detail": "failed"}],
            repaired=True,
        )
    counters.usage.input_tokens += final.extra_input_tokens
    counters.usage.output_tokens += final.extra_output_tokens
    yield LoopFinished(
        text=final.text,
        grounding=final.grounding,
        citations=final.citations or parse_markup(final.text),
        tools_used=_tools_used(ran),
        data_as_of=_as_of([result for _, result in ran], context),
        flags=final.flags,
        usage=counters.usage,
        rounds=counters.rounds,
        tool_call_count=counters.tool_calls,
        repaired=final.repaired,
        disclaimers=final.disclaimers,
    )


def _shorten(text: str) -> str:
    clipped = text[:1800]
    stop = clipped.rfind(". ")
    if stop > 400:
        return clipped[: stop + 1] + " (shortened)"
    return clipped.rstrip() + " (shortened)" if len(text) > 1800 else text


def _question_text(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.role == "user" and message.content != FORCE_FINAL_INSTRUCTION:
            return message.content
    return ""


def _corpus(
    context: ContextView,
    ran: list[tuple[ToolCall, ToolResult]],
    *,
    canary: str,
    prompt_text: str,
    user_text: str,
) -> Corpus:
    from fplcore.chat.guard import corpus_from_turn

    results = [result for _, result in ran]
    gws = {context.decision_gw} if context.decision_gw else set()
    if context.started_gw:
        gws.add(context.started_gw)
    return corpus_from_turn(
        context_text=context_text(context),
        context_ids=context.player_ids,
        names=dict(context.names),
        gws=gws,
        results=results,
        canary=canary,
        prompt_text=prompt_text,
        fallback_text=fallback_from_results(results, headline=context.plan_headline),
        user_text=user_text,
    )


def context_text(context: ContextView) -> str:
    from fplcore.chat.prompt import render_context

    return render_context(context)
