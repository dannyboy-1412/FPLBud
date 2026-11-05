from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from fplcore.chat.events import MessageDelta, StatusEvent, ToolEnd, ToolStart
from fplcore.chat.loop import LoopFailed, LoopFinished, run_turn
from fplcore.chat.prompt import ContextView
from fplcore.chat.registry import BoundTool, ToolRegistry, null_connection
from fplcore.chat.testing import ScriptedLlm, text_turn, tool_turn
from fplcore.chat.types import ChatCfg, Message, ToolContext, ToolResult, failure


class _Empty(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Echo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: int


def _ctx() -> ToolContext:
    return ToolContext(
        user_id="user-1",
        entry_id=1,
        season_id="2026/27",
        weights={},
        snapshot_id=1,
        data_version=1,
        now=datetime(2026, 10, 25, tzinfo=UTC),
        has_team=True,
    )


def _registry(*tools: BoundTool, **kwargs: Any) -> ToolRegistry:
    return ToolRegistry(list(tools), open_conn=null_connection, **kwargs)


def _echo_tool(calls: list[int]) -> BoundTool:
    def handler(ctx: ToolContext, args: BaseModel, conn: object) -> ToolResult:
        del ctx, conn
        assert isinstance(args, _Echo)
        calls.append(args.player_id)
        return ToolResult(ok=True, data={"id": args.player_id, "name": "Haaland", "proj": 7.4}, as_of="2026-10-25T05:10:00Z")

    return BoundTool("get_player", "Look up one player.", _Echo, handler)


async def _collect(llm: ScriptedLlm, tools: ToolRegistry, cfg: ChatCfg | None = None) -> list[object]:
    events = []
    async for event in run_turn(
        [],
        llm=llm,
        tools=tools,
        cfg=cfg or ChatCfg(max_rounds=4, max_tool_calls=6, turn_timeout_s=30),
        ctx=_ctx(),
        context=ContextView(decision_gw=9, data_as_of="2026-10-25T05:10:00Z", names={12: "Haaland"}),
    ):
        events.append(event)
    return events


async def test_answer_without_tools_streams_then_finishes() -> None:
    llm = ScriptedLlm([text_turn("Captain [[p:12|Haaland]]. Data as of 2026-10-25T05:10:00Z.")])
    events = await _collect(llm, _registry())
    assert any(isinstance(event, MessageDelta) and "Haaland" in event.text for event in events)
    final = events[-1]
    assert isinstance(final, LoopFinished)
    assert final.grounding == "ok"
    assert final.citations[0].player_id == 12
    assert llm.tools_sent == [[]] or llm.tools_sent[0] == []


async def test_tool_call_then_answer() -> None:
    seen: list[int] = []
    llm = ScriptedLlm(
        [
            tool_turn(("c1", "get_player", {"player_id": 12})),
            text_turn("Captain [[p:12|Haaland]] projects 7.4 points."),
        ]
    )
    events = await _collect(llm, _registry(_echo_tool(seen)))
    assert seen == [12]
    assert any(isinstance(event, ToolStart) and event.label == "Looking up Haaland" or event.name == "get_player" for event in events if isinstance(event, ToolStart))
    assert any(isinstance(event, ToolEnd) and event.ok for event in events)
    final = events[-1]
    assert isinstance(final, LoopFinished)
    assert final.tool_call_count == 1
    assert final.tools_used[0]["name"] == "get_player"


async def test_identical_calls_are_memoised() -> None:
    seen: list[int] = []
    llm = ScriptedLlm(
        [
            tool_turn(
                ("c1", "get_player", {"player_id": 12}),
                ("c2", "get_player", {"player_id": 12}),
            ),
            text_turn("Noted."),
        ]
    )
    events = await _collect(llm, _registry(_echo_tool(seen)))
    assert seen == [12]
    ends = [event for event in events if isinstance(event, ToolEnd)]
    assert len(ends) == 2
    final = events[-1]
    assert isinstance(final, LoopFinished)
    assert final.tool_call_count == 2


async def test_unknown_tool_is_an_error_result_and_then_forced() -> None:
    llm = ScriptedLlm(
        [
            tool_turn(("c1", "not_a_tool", {})),
            tool_turn(("c2", "still_no", {})),
            text_turn("I can't look that up."),
        ]
    )
    events = await _collect(llm, _registry(), ChatCfg(max_rounds=4, max_tool_calls=6, turn_timeout_s=30))
    final = events[-1]
    assert isinstance(final, LoopFinished)
    assert "look that up" in final.text
    assert llm.tools_sent[-1] is None


async def test_tool_cap_forces_a_final_answer() -> None:
    seen: list[int] = []
    llm = ScriptedLlm(
        [
            tool_turn(("c1", "get_player", {"player_id": 12})),
            text_turn("That's enough."),
        ]
    )
    events = await _collect(
        llm,
        _registry(_echo_tool(seen)),
        ChatCfg(max_rounds=4, max_tool_calls=1, turn_timeout_s=30),
    )
    final = events[-1]
    assert isinstance(final, LoopFinished)
    assert final.text == "That's enough."
    assert llm.tools_sent[1] is None


async def test_provider_failure_before_tools_is_an_error() -> None:
    class _Down(ScriptedLlm):
        async def stream(self, messages, *, tools, max_tokens, temperature=0.2, on_text=None):  # type: ignore[no-untyped-def]
            from fplcore.chat.model import LlmError

            raise LlmError("http 503", status=503, retryable=True)

    events = await _collect(_Down([]), _registry())
    assert isinstance(events[-1], LoopFailed)
    assert events[-1].code == "UNAVAILABLE"
    assert events[-1].retryable is True


async def test_parallel_tools_run() -> None:
    seen: list[int] = []
    llm = ScriptedLlm(
        [
            tool_turn(
                ("c1", "get_player", {"player_id": 12}),
                ("c2", "get_player", {"player_id": 5}),
            ),
            text_turn("Both checked."),
        ]
    )
    events = await _collect(llm, _registry(_echo_tool(seen)))
    assert sorted(seen) == [5, 12]
    assert [event.phase for event in events if isinstance(event, StatusEvent)][0] == "thinking"


def test_connection_is_not_held_during_the_model_call() -> None:
    open_now = {"n": 0}

    @contextmanager
    def opener():  # type: ignore[no-untyped-def]
        open_now["n"] += 1
        try:
            yield object()
        finally:
            open_now["n"] -= 1

    seen: list[int] = []

    def handler(ctx: ToolContext, args: BaseModel, conn: object) -> ToolResult:
        del ctx
        assert conn is not None
        assert isinstance(args, _Echo)
        seen.append(args.player_id)
        return ToolResult(ok=True, data={"id": args.player_id})

    tool = BoundTool("get_player", "Look up one player.", _Echo, handler)
    registry = ToolRegistry([tool], open_conn=opener)
    llm = ScriptedLlm(
        [
            tool_turn(("c1", "get_player", {"player_id": 12})),
            text_turn("Done."),
        ]
    )

    def during_stream() -> None:
        assert open_now["n"] == 0

    llm.on_stream = during_stream

    async def go() -> None:
        async for _event in run_turn(
            [],
            llm=llm,
            tools=registry,
            cfg=ChatCfg(max_rounds=3, turn_timeout_s=30),
            ctx=_ctx(),
            context=ContextView(),
        ):
            pass

    import asyncio

    asyncio.run(go())
    assert seen == [12]


def test_invalid_arguments_do_not_call_the_handler() -> None:
    def handler(ctx: ToolContext, args: BaseModel, conn: object) -> ToolResult:
        del ctx, args, conn
        raise AssertionError("handler should not run")

    tool = BoundTool("get_player", "Look up one player.", _Echo, handler)

    async def go() -> LoopFinished:
        llm = ScriptedLlm(
            [
                tool_turn(("c1", "get_player", {"player_id": "nope"})),
                text_turn("Ask with an id."),
            ]
        )
        events = await _collect(llm, _registry(tool), ChatCfg(max_rounds=3, turn_timeout_s=30))
        final = events[-1]
        assert isinstance(final, LoopFinished)
        return final

    import asyncio

    final = asyncio.run(go())
    assert "id" in final.text


def test_handler_exception_becomes_internal() -> None:
    def handler(ctx: ToolContext, args: BaseModel, conn: object) -> ToolResult:
        del ctx, args, conn
        raise RuntimeError("db down")

    tool = BoundTool("get_player", "Look up one player.", _Echo, handler)

    async def go() -> str:
        llm = ScriptedLlm(
            [
                tool_turn(("c1", "get_player", {"player_id": 1})),
                text_turn("Without that lookup: I don't know."),
            ]
        )
        events = await _collect(llm, _registry(tool))
        tool_msgs = llm.seen[-1]
        contents = [message.content for message in tool_msgs if message.role == "tool"]
        assert contents and "INTERNAL" in contents[0]
        final = events[-1]
        assert isinstance(final, LoopFinished)
        return final.text

    import asyncio

    assert "don't know" in asyncio.run(go())


def test_squad_answer_names_the_player_when_the_chip_has_no_id() -> None:
    async def go() -> LoopFinished:
        llm = ScriptedLlm([text_turn("No—[[?]] isn't in your saved squad.")])
        events: list[object] = []
        async for event in run_turn(
            [Message(role="user", content="do I have szoboslai in my team?")],
            llm=llm,
            tools=_registry(),
            cfg=ChatCfg(max_rounds=2, max_tool_calls=2, turn_timeout_s=30),
            ctx=_ctx(),
            context=ContextView(decision_gw=11, data_as_of="2026-11-05T06:59:00Z"),
        ):
            events.append(event)
        final = events[-1]
        assert isinstance(final, LoopFinished)
        return final

    import asyncio

    finished = asyncio.run(go())
    assert finished.text == "No—szoboslai isn't in your saved squad."
    assert finished.citations == []


def test_failure_helper_shape() -> None:
    result = failure("NO_TEAM_SAVED", "No squad is saved.", hint="Add a team at /onboarding.")
    text = result.to_model_text()
    assert '"ok":false' in text
    assert "NO_TEAM_SAVED" in text
