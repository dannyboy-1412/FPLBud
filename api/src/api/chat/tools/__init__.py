"""Read-only tools. Identity comes from ToolContext, never from the model."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.chat.tools.compare import compare_players
from api.chat.tools.fixtures import get_fixtures
from api.chat.tools.gameweek import get_gameweek_context
from api.chat.tools.insights import get_insights
from api.chat.tools.market import get_market_movers
from api.chat.tools.my_team import get_my_team
from api.chat.tools.plan import evaluate_transfer, get_plan_suggestions, run_transfer_optimiser
from api.chat.tools.player import get_player
from api.chat.tools.preference import save_preference
from api.chat.tools.rules import explain_topic
from api.chat.tools.search import search_players
from fplcore.chat.registry import BoundTool, ToolRegistry
from fplcore.db import chat_repo
from fplcore.settings import Settings

ConnFactory = Callable[[], Any]


def tool_set() -> list[BoundTool]:
    return [
        get_gameweek_context,
        get_my_team,
        search_players,
        get_player,
        compare_players,
        get_fixtures,
        get_market_movers,
        get_insights,
        explain_topic,
        get_plan_suggestions,
        run_transfer_optimiser,
        evaluate_transfer,
        save_preference,
    ]


def build_registry(
    open_conn: ConnFactory,
    settings: Settings,
    *,
    db_slots: int,
) -> ToolRegistry:
    return ToolRegistry(
        tool_set(),
        open_conn=open_conn,
        db_slots=db_slots,
        optimiser_slots=1,
        max_optimiser_calls=2,
        result_soft_cap=settings.chat_tool_result_token_cap,
        result_hard_cap=max(settings.chat_tool_result_token_cap * 2, 3000),
        record_span=_span(settings),
    )


def _span(settings: Settings) -> Callable[[Any, dict[str, Any]], None]:
    def record(conn: Any, payload: dict[str, Any]) -> None:
        result = payload.get("result") if settings.chat_store_tool_results else None
        chat_repo.record_tool_call(
            conn,
            turn_id=int(payload["turn_id"]),
            round_no=int(payload["round"]),
            name=str(payload["name"]),
            args=payload.get("args"),
            ok=bool(payload["ok"]),
            error_code=payload.get("error_code"),
            result_tokens=payload.get("result_tokens"),
            result=result if isinstance(result, dict) else None,
            duration_ms=payload.get("duration_ms"),
        )

    return record
