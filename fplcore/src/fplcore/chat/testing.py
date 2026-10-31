from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fplcore.chat.types import Message, ModelTurn, Usage


class ScriptedLlm:
    """Deterministic stand-in. Each stream() call pops the next scripted turn."""

    def __init__(self, turns: list[ModelTurn]) -> None:
        self.turns = list(turns)
        self.seen: list[list[Message]] = []
        self.tools_sent: list[list[dict[str, Any]] | None] = []
        self.on_stream: Callable[[], None] | None = None

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float = 0.2,
        on_text: Callable[[str], None] | None = None,
    ) -> ModelTurn:
        del max_tokens, temperature
        if self.on_stream is not None:
            self.on_stream()
        self.seen.append(list(messages))
        self.tools_sent.append(tools)
        if not self.turns:
            raise RuntimeError("script exhausted")
        turn = self.turns.pop(0)
        if on_text is not None and turn.text and not turn.tool_calls:
            on_text(turn.text)
        elif on_text is not None and turn.text and turn.tool_calls:
            on_text(turn.text)
        return turn


def text_turn(text: str, *, model: str = "scripted") -> ModelTurn:
    return ModelTurn(text=text, tool_calls=[], finish_reason="stop", usage=Usage(12, 8), model=model)


def tool_turn(*calls: tuple[str, str, dict[str, Any]], text: str = "", model: str = "scripted") -> ModelTurn:
    from fplcore.chat.types import ToolCall

    parsed = [
        ToolCall(id=call_id, name=name, arguments=args, raw_arguments="")
        for call_id, name, args in calls
    ]
    return ModelTurn(
        text=text,
        tool_calls=parsed,
        finish_reason="tool_calls",
        usage=Usage(20, 10),
        model=model,
    )
