import json
from pathlib import Path

from fplcore.chat.events import PROTOCOL_VERSION, event_contract

SCHEMA = Path("contracts/chat/events.schema.json")


def test_committed_schema_matches_the_code() -> None:
    committed = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert committed == event_contract()
    assert committed["protocol_version"] == PROTOCOL_VERSION == "1"
    assert set(committed["events"]) == {
        "turn.start",
        "status",
        "tool.start",
        "tool.end",
        "message.delta",
        "message.final",
        "memory.proposal",
        "usage",
        "error",
        "done",
    }
