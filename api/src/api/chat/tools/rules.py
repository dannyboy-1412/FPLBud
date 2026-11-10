from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from api.chat.tools.common import ok
from fplcore.chat.knowledge import TOPICS, explain
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure

TopicName = Literal["squad", "transfers", "hits", "chips", "deadlines", "prices", "projections"]


class TopicArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: TopicName


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    del conn
    parsed = TopicArgs.model_validate(args.model_dump())
    card = explain(parsed.topic)
    if card is None:
        return failure(
            "INVALID_ARGUMENT",
            "No rule card for that topic.",
            hint="Topics: " + ", ".join(sorted(TOPICS)),
        )
    return ok(card, as_of=card["last_verified"], data_version=ctx.data_version)


explain_topic = BoundTool(
    name="explain_topic",
    description=(
        "Official-style rules for squad, transfers, hits, chips, deadlines or prices, "
        "and how FPLBud projects points. Quote this instead of guessing."
    ),
    args_model=TopicArgs,
    handler=_run,
)
