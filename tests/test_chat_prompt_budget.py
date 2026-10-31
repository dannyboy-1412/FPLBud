import json

from api.chat.tools import tool_set
from fplcore.chat.budget import estimate_tokens
from fplcore.chat.prompt import SYSTEM_PROMPT, ContextView, render_context
from fplcore.chat.registry import strict_schema
from fplcore.chat.types import ChatCfg


def test_tools_and_context_fit_under_the_turn_cap() -> None:
    parts = [SYSTEM_PROMPT, render_context(ContextView(season_id="2026/27", decision_gw=9, has_team=True))]
    for tool in tool_set():
        parts.append(tool.name)
        parts.append(tool.description)
        parts.append(json.dumps(strict_schema(tool.args_model), sort_keys=True))
    assert estimate_tokens("\n".join(parts)) < ChatCfg().turn_input_token_cap
    assert len(tool_set()) == 13
