"""Resolve names in the user's message and append them to this turn's context."""

from __future__ import annotations

import logging
from typing import Any

from api.chat.context import pounds
from fplcore.chat.names import NameRecord, insert_mentioned, mentioned_in
from fplcore.chat.prompt import ContextView
from fplcore.chat.types import Message
from fplcore.constants import POSITION_SHORT

logger = logging.getLogger("fplbud.chat")


def apply_mentions(conn: Any, text: str, view: ContextView, messages: list[Message]) -> None:
    if not text or not view.season_id:
        return
    players = _records(conn, view.season_id)
    if not players:
        return
    found = mentioned_in(text, players)
    for player_id, name in found.resolved.items():
        view.names.setdefault(player_id, name)
    if not found.line:
        return
    for message in messages:
        if message.role == "user" and "<context" in message.content:
            message.content = insert_mentioned(message.content, found.line)
            return


def _records(conn: Any, season_id: str) -> list[NameRecord]:
    try:
        rows = conn.execute(
            """
            select p.id, p.web_name, p.first_name, p.second_name, p.now_cost, p.position_id,
                   t.short_name as team_short
              from players p
              join teams t on t.season_id = p.season_id and t.id = p.team_id
             where p.season_id = %s and p.removed = false
            """,
            [season_id],
        ).fetchall()
    except Exception:
        logger.exception("chat name resolution unavailable")
        return []
    records: list[NameRecord] = []
    for row in rows:
        records.append(
            NameRecord(
                player_id=int(row["id"]),
                web_name=str(row["web_name"] or ""),
                first_name=str(row["first_name"] or ""),
                second_name=str(row["second_name"] or ""),
                team=str(row["team_short"] or ""),
                position=POSITION_SHORT.get(int(row["position_id"]), "?"),
                price_m=pounds(row["now_cost"]) or 0.0,
            )
        )
    return records
