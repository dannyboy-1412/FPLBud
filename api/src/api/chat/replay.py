"""Print one saved turn. Refused in production unless CHAT_ADMIN_USER_IDS is set."""

from __future__ import annotations

import json
import sys
from typing import Any

from fplcore.db import chat_repo
from fplcore.db.connection import connect
from fplcore.settings import Settings, get_settings


def replay_allowed(settings: Settings) -> bool:
    if settings.is_production and not settings.chat_admin_ids:
        return False
    return True


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    settings = get_settings()
    if not replay_allowed(settings):
        raise SystemExit("Replay is refused in production while CHAT_ADMIN_USER_IDS is empty.")
    if len(args) != 1 or not args[0].isdigit():
        raise SystemExit("Usage: python -m api.chat.replay <turn_id>")
    with connect(settings) as conn:
        trace = chat_repo.load_turn_trace(conn, int(args[0]))
    if trace is None:
        raise SystemExit("Turn not found.")
    print(json.dumps(_public(trace), indent=2, default=str))


def _public(trace: dict[str, Any]) -> dict[str, Any]:
    turn = dict(trace.get("turn") or {})
    turn.pop("user_id", None)
    return {
        "turn": turn,
        "messages": trace.get("messages") or [],
        "tool_calls": trace.get("tool_calls") or [],
    }


if __name__ == "__main__":
    main()
