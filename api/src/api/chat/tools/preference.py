from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.chat.tools.common import ok
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.db import chat_repo
from fplcore.db.chat_repo import MEMORY_KEYS

_LABELS = {
    "risk_appetite": "Risk appetite",
    "favourite_team": "Favourite club",
    "avoid_player_ids": "Players to avoid",
    "prefers_differentials": "Prefer differentials",
    "notes_short": "Note",
}


class PreferenceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    value: str = Field(max_length=80)


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    parsed = PreferenceArgs.model_validate(args.model_dump())
    if parsed.key not in MEMORY_KEYS:
        return failure("INVALID_ARGUMENT", "That is not a preference I can save.", hint=", ".join(sorted(MEMORY_KEYS)))
    thread_id = _thread(ctx)
    if thread_id is None:
        return failure("INTERNAL", "This question has no thread to attach the preference to.")
    proposal_id = chat_repo.propose_memory(
        conn,
        user_id=ctx.user_id,
        thread_id=thread_id,
        key=parsed.key,
        value=parsed.value,
    )
    if proposal_id is None:
        return failure("INVALID_ARGUMENT", "I could not store that preference.")
    return ok(
        {
            "proposal_id": proposal_id,
            "key": parsed.key,
            "value": parsed.value.strip()[:80],
            "label": _LABELS.get(parsed.key, parsed.key),
        },
        as_of=None,
        data_version=ctx.data_version,
        notes=["The user must confirm this before it is saved."],
    )


def _thread(ctx: ToolContext) -> str | None:
    return ctx.thread_id or None


save_preference = BoundTool(
    name="save_preference",
    description="Propose a preference for the user to confirm. Does not save it until they accept.",
    args_model=PreferenceArgs,
    handler=_run,
)
