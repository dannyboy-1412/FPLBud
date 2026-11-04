"""Turn stored rows back into model messages. Tool bodies stay server-side."""

from __future__ import annotations

from typing import Any

from api.chat.context import fingerprint, view_from_fingerprint
from fplcore.chat.budget import clear_old_tool_results, trim_history
from fplcore.chat.prompt import ContextView, render_context, render_context_update, system_prompt
from fplcore.chat.types import Message, ToolCall


def message_from_row(row: dict[str, Any]) -> Message:
    calls: list[ToolCall] = []
    raw_calls = row.get("tool_calls") or []
    if isinstance(raw_calls, list):
        for item in raw_calls:
            if not isinstance(item, dict):
                continue
            arguments = item.get("arguments")
            calls.append(
                ToolCall(
                    id=str(item.get("id") or ""),
                    name=str(item.get("name") or ""),
                    arguments=arguments if isinstance(arguments, dict) else None,
                    raw_arguments=str(item.get("raw_arguments") or ""),
                )
            )
    turn_id = row.get("turn_id")
    return Message(
        role=row["role"],
        content=str(row.get("content") or ""),
        tool_calls=calls,
        tool_call_id=row.get("tool_call_id"),
        turn_index=int(turn_id) if turn_id is not None else None,
    )


def rows_for_round(assistant: Message, tool_messages: list[Message]) -> list[dict[str, Any]]:
    assistant_row: dict[str, Any] = {
        "role": "assistant",
        "content": assistant.content,
        "tool_calls": [
            {
                "id": call.id,
                "name": call.name,
                "arguments": call.arguments,
                "raw_arguments": call.raw_arguments,
            }
            for call in assistant.tool_calls
        ],
    }
    tool_rows = [
        {
            "role": "tool",
            "content": message.content,
            "tool_call_id": message.tool_call_id,
        }
        for message in tool_messages
    ]
    return [assistant_row, *tool_rows]


def prompt_messages(
    *,
    canary: str,
    view: ContextView,
    stored_context: dict[str, Any] | None,
    history_rows: list[dict[str, Any]],
    history_budget: int,
) -> tuple[list[Message], str, dict[str, Any] | None, str | None]:
    """System prompt, pinned context, trimmed history, and an optional update to persist.

    Returns messages, the pinned text, a context payload when it still needs writing, and the update.
    """
    pinned_text, previous = _pinned(stored_context, view)
    squad_moved = isinstance(stored_context, dict) and previous.snapshot_id != view.snapshot_id
    if squad_moved:
        pinned_text = render_context(view)
    to_pin = None
    if stored_context is None or squad_moved:
        to_pin = {"text": pinned_text, "fingerprint": fingerprint(view)}
    history = [message_from_row(row) for row in history_rows]
    history = trim_history(clear_old_tool_results(history), budget=history_budget)
    update = render_context_update(previous, view)
    if update and any(message.role == "system" and message.content == update for message in history):
        update = None
    current = history[-1] if history and history[-1].role == "user" else None
    earlier = history[:-1] if current is not None else history
    messages = [
        Message(role="system", content=system_prompt(canary)),
        Message(role="user", content=pinned_text),
        *earlier,
    ]
    if update:
        messages.append(Message(role="system", content=update))
    if current is not None:
        messages.append(current)
    return messages, pinned_text, to_pin, update


def _pinned(stored: dict[str, Any] | None, view: ContextView) -> tuple[str, ContextView]:
    if isinstance(stored, dict) and isinstance(stored.get("text"), str):
        raw = stored.get("fingerprint")
        previous = view_from_fingerprint(raw) if isinstance(raw, dict) else ContextView()
        return stored["text"], previous
    return render_context(view), view
