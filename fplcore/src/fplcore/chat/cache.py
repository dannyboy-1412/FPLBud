"""One projection cache for a chat turn. ToolContext stays plain data."""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnCache:
    data_version: int | None = None
    ranked: dict[tuple[Any, ...], list[dict[str, Any]]] = field(default_factory=dict)
    opt: dict[tuple[Any, ...], list[Any]] = field(default_factory=dict)
    lineup: dict[str, Any] | None = None
    lineup_loaded: bool = False
    as_of: str | None = None
    as_of_loaded: bool = False


_current: ContextVar[TurnCache | None] = ContextVar("fplbud_chat_turn_cache", default=None)


def current_cache() -> TurnCache | None:
    return _current.get()


def activate_cache(cache: TurnCache) -> Token[TurnCache | None]:
    return _current.set(cache)


def reset_cache(token: Token[TurnCache | None]) -> None:
    _current.reset(token)


def weights_key(weights: dict[str, float]) -> str:
    clean = {str(key): float(value) for key, value in weights.items()}
    return json.dumps(clean, sort_keys=True, separators=(",", ":"))
