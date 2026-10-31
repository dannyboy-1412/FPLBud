"""One committed SSE transcript. The web parser is tested against this file."""

from __future__ import annotations

from pathlib import Path

from api.chat.sse import frame
from fplcore.chat.events import (
    Citation,
    DoneEvent,
    MessageDelta,
    MessageFinal,
    ToolUse,
    TurnStart,
    UsageEvent,
)

PATH = Path(__file__).resolve().parents[2] / "contracts" / "chat" / "sse" / "deadline.sse"


def transcript() -> str:
    events = [
        TurnStart(
            turn_id=1,
            thread_id="thread",
            user_message_id=2,
            prompt_version="2026-10-31a",
            model="scripted",
        ),
        MessageDelta(text="The deadline is Saturday.", round=1, attempt=1),
        MessageFinal(
            message_id=3,
            text="The deadline is Saturday. [[p:13|Haaland]] is your captain.",
            citations=[Citation(player_id=13, name="Haaland", team="MCI", price_m=15.0)],
            data_as_of="2026-10-25T12:00:00Z",
            tools_used=[ToolUse(name="get_gameweek_context", args_brief="{}")],
            grounding="ok",
            disclaimers=[],
        ),
        UsageEvent(turns_left_today=19, tokens={"input": 12, "output": 8, "cached": 0}),
        DoneEvent(turn_id=1, status="ok"),
    ]
    return "".join(frame(event) for event in events)


def write() -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(transcript(), encoding="utf-8")


if __name__ == "__main__":
    write()
