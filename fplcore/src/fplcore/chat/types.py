from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

FinishReason = Literal["stop", "tool_calls", "length", "content_filter", "error"]
GroundingState = Literal["ok", "repaired", "fallback"]

OPTIMISER_TOOL = "run_transfer_optimiser"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float | None = None

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_tokens += other.cached_tokens
        if other.cost_usd is not None:
            self.cost_usd = (self.cost_usd or 0.0) + other.cost_usd


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] | None = None
    raw_arguments: str = ""
    parse_error: str | None = None

    def canonical_args(self) -> str:
        if self.arguments is None:
            return self.raw_arguments
        return json.dumps(self.arguments, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    turn_index: int | None = None

    def to_api(self) -> dict[str, Any]:
        if self.role == "assistant" and self.tool_calls:
            return {
                "role": "assistant",
                "content": self.content or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": call.raw_arguments or call.canonical_args(),
                        },
                    }
                    for call in self.tool_calls
                ],
            }
        if self.role == "tool":
            body: dict[str, Any] = {
                "role": "tool",
                "content": self.content,
                "tool_call_id": self.tool_call_id or "",
            }
            return body
        return {"role": self.role, "content": self.content}


@dataclass
class ToolErrorInfo:
    code: str
    message: str
    hint: str | None = None
    candidates: list[dict[str, Any]] | None = None


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: ToolErrorInfo | None = None
    as_of: str | None = None
    data_version: int | None = None
    notes: list[str] = field(default_factory=list)
    truncated: bool = False
    duration_ms: int = 0
    injection_suspected: bool = False

    def envelope(self) -> dict[str, Any]:
        if not self.ok:
            err: dict[str, Any] = {
                "code": self.error.code if self.error else "INTERNAL",
                "message": self.error.message if self.error else "The tool failed.",
            }
            if self.error and self.error.hint:
                err["hint"] = self.error.hint
            if self.error and self.error.candidates:
                err["candidates"] = self.error.candidates
            return {"ok": False, "error": err}
        return {
            "ok": True,
            "data": self.data or {},
            "as_of": self.as_of,
            "data_version": self.data_version,
            "notes": self.notes,
            "truncated": self.truncated,
        }

    def to_model_text(self) -> str:
        return json.dumps(self.envelope(), separators=(",", ":"), default=str)


def failure(
    code: str,
    message: str,
    *,
    hint: str | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> ToolResult:
    return ToolResult(ok=False, error=ToolErrorInfo(code, message, hint, candidates))


@dataclass
class ModelTurn:
    text: str
    tool_calls: list[ToolCall]
    finish_reason: FinishReason
    usage: Usage
    model: str

    def as_assistant_message(self, *, turn_index: int | None = None) -> Message:
        return Message(
            role="assistant",
            content=self.text,
            tool_calls=list(self.tool_calls),
            turn_index=turn_index,
        )


@dataclass
class ToolContext:
    user_id: str
    entry_id: int | None
    season_id: str | None
    weights: dict[str, float]
    snapshot_id: int | None
    data_version: int | None
    now: datetime
    has_team: bool = False
    max_hits: int = 1
    default_horizon: int = 1
    onboarded: bool = False
    thread_id: str = ""
    optimiser_hourly_cap: int = 20
    cache: Any = None


@dataclass
class ChatCfg:
    max_rounds: int = 6
    max_tool_calls: int = 10
    max_optimiser_calls: int = 2
    turn_timeout_s: float = 60.0
    max_output_tokens: int = 900
    turn_input_token_cap: int = 40_000
    max_input_chars: int = 1500
    history_token_budget: int = 6000
    tool_result_token_cap: int = 1500
    tool_result_hard_cap: int = 3000
    temperature: float = 0.2
    model: str = ""
    fallback_model: str = ""


@dataclass
class TurnCounters:
    rounds: int = 0
    tool_calls: int = 0
    optimiser_calls: int = 0
    invalid_streak: int = 0
    usage: Usage = field(default_factory=Usage)


@dataclass
class Corpus:
    """Facts a final answer is allowed to use."""

    context_text: str = ""
    results: list[ToolResult] = field(default_factory=list)
    player_ids: set[int] = field(default_factory=set)
    names: dict[int, str] = field(default_factory=dict)
    seen_names: set[str] = field(default_factory=set)
    numbers: set[str] = field(default_factory=set)
    prices: set[float] = field(default_factory=set)
    projections: set[float] = field(default_factory=set)
    gws: set[int] = field(default_factory=set)
    canary: str = ""
    fallback_text: str = ""
    prompt_text: str = ""
    user_text: str = ""
