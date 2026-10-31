from __future__ import annotations

import math

from fplcore.chat.types import Message

CHARS_PER_TOKEN = 3.6
TOKEN_MARGIN = 1.15


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def estimate_tokens_with_margin(text: str) -> int:
    return math.ceil(estimate_tokens(text) * TOKEN_MARGIN)


def messages_tokens(messages: list[Message]) -> int:
    total = 0
    for message in messages:
        total += estimate_tokens(message.content)
        for call in message.tool_calls:
            total += estimate_tokens(call.name) + estimate_tokens(call.canonical_args())
    return total


def clear_old_tool_results(messages: list[Message], *, keep_turns: int = 2) -> list[Message]:
    """Replace tool payloads from turns older than the last `keep_turns` with stubs."""
    indexes = [message.turn_index for message in messages if message.turn_index is not None]
    if not indexes:
        return list(messages)
    latest = max(indexes)
    cutoff = latest - (keep_turns - 1)
    cleared: list[Message] = []
    for message in messages:
        stale = (
            message.role == "tool"
            and message.turn_index is not None
            and message.turn_index < cutoff
        )
        if not stale:
            cleared.append(message)
            continue
        name = message.name or "tool"
        cleared.append(
            Message(
                role="tool",
                content=f"[tool {name} returned; result cleared]",
                tool_call_id=message.tool_call_id,
                name=message.name,
                turn_index=message.turn_index,
            )
        )
    return cleared


def _turn_groups(messages: list[Message]) -> list[list[Message]]:
    groups: list[list[Message]] = []
    current: list[Message] = []
    for message in messages:
        if message.role == "user" and current:
            groups.append(current)
            current = [message]
        else:
            current.append(message)
    if current:
        groups.append(current)
    return groups


def trim_history(messages: list[Message], *, budget: int, keep_last_turns: int = 3) -> list[Message]:
    """Drop oldest turns until the history fits. Keeps the first user turn and the last few."""
    cleared = clear_old_tool_results(messages)
    groups = _turn_groups(cleared)
    if messages_tokens(cleared) <= budget or len(groups) <= keep_last_turns + 1:
        return cleared
    while len(groups) > keep_last_turns + 1 and messages_tokens(_flatten(groups)) > budget:
        del groups[1]
    return _flatten(groups)


def _flatten(groups: list[list[Message]]) -> list[Message]:
    flat: list[Message] = []
    for group in groups:
        flat.extend(group)
    return flat
