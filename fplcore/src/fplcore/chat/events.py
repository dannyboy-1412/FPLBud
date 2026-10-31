from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

PROTOCOL_VERSION = "1"

_EVENT_MODELS: dict[str, type[BaseModel]] = {}


def _event(name: str) -> Any:
    def wrap(cls: type[BaseModel]) -> type[BaseModel]:
        cls.__event_name__ = name  # type: ignore[attr-defined]
        _EVENT_MODELS[name] = cls
        return cls

    return wrap


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid")


@_event("turn.start")
class TurnStart(_Event):
    turn_id: int
    thread_id: str
    user_message_id: int
    prompt_version: str
    model: str
    protocol_version: str = PROTOCOL_VERSION


@_event("status")
class StatusEvent(_Event):
    phase: Literal["thinking", "tool", "checking"]


@_event("tool.start")
class ToolStart(_Event):
    call_id: str
    name: str
    label: str


@_event("tool.end")
class ToolEnd(_Event):
    call_id: str
    ok: bool
    ms: int
    summary: str | None = None


@_event("message.delta")
class MessageDelta(_Event):
    text: str
    round: int
    attempt: int = 1


class Citation(_Event):
    player_id: int
    name: str
    team: str | None = None
    price_m: float | None = None


class ToolUse(_Event):
    name: str
    args_brief: str


@_event("message.final")
class MessageFinal(_Event):
    message_id: int
    text: str
    citations: list[Citation]
    data_as_of: str | None = None
    tools_used: list[ToolUse]
    grounding: Literal["ok", "repaired", "fallback"]
    disclaimers: list[str] = []


@_event("memory.proposal")
class MemoryProposalEvent(_Event):
    proposal_id: int
    key: str
    value: str
    label: str


@_event("usage")
class UsageEvent(_Event):
    turns_left_today: int
    tokens: dict[str, int]


@_event("error")
class ErrorEvent(_Event):
    code: str
    message: str
    retryable: bool
    turns_left_today: int | None = None


@_event("done")
class DoneEvent(_Event):
    turn_id: int
    status: str


ChatEvent = (
    TurnStart
    | StatusEvent
    | ToolStart
    | ToolEnd
    | MessageDelta
    | MessageFinal
    | MemoryProposalEvent
    | UsageEvent
    | ErrorEvent
    | DoneEvent
)


def event_name(event: BaseModel) -> str:
    name = getattr(event, "__event_name__", None)
    if not isinstance(name, str):
        raise TypeError(f"not a chat event: {type(event).__name__}")
    return name


def event_payload(event: BaseModel) -> dict[str, Any]:
    return event.model_dump(mode="json")


def event_contract() -> dict[str, Any]:
    """Stable description of the SSE payloads. Clients and the TUI test against this."""
    # Citation and ToolUse are nested models, not events. Registering MessageFinal
    # twice would be wrong; Citation was decorated by mistake if we did that.
    events = {
        "turn.start": TurnStart.model_json_schema(),
        "status": StatusEvent.model_json_schema(),
        "tool.start": ToolStart.model_json_schema(),
        "tool.end": ToolEnd.model_json_schema(),
        "message.delta": MessageDelta.model_json_schema(),
        "message.final": MessageFinal.model_json_schema(),
        "memory.proposal": MemoryProposalEvent.model_json_schema(),
        "usage": UsageEvent.model_json_schema(),
        "error": ErrorEvent.model_json_schema(),
        "done": DoneEvent.model_json_schema(),
    }
    return {"protocol_version": PROTOCOL_VERSION, "events": events}
