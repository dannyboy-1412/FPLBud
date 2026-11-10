from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, get_args

from pydantic import BaseModel, ConfigDict

from api.chat.tools import tool_set
from api.chat.tools.fixtures import build_ticker
from api.chat.tools.insights import InsightArgs, get_insights
from api.chat.tools.market import MarketArgs, get_market_movers
from api.chat.tools.plan import shape_saved_plan
from api.chat.tools.preference import PreferenceKey
from api.chat.tools.rules import TopicName
from api.services import ranked_players
from fplcore.chat.cache import TurnCache, activate_cache, reset_cache
from fplcore.chat.knowledge import TOPICS
from fplcore.chat.loop import LoopFinished, run_turn
from fplcore.chat.moves import Candidate, MoveInput, quote_transfers, rank_replacements
from fplcore.chat.names import NameRecord, fold, insert_mentioned, match_query, mentioned_in
from fplcore.chat.prefetch import prefetch_tool
from fplcore.chat.prompt import SYSTEM_PROMPT, ContextView
from fplcore.chat.registry import BoundTool, ToolRegistry, null_connection, strict_schema
from fplcore.chat.testing import ScriptedLlm, text_turn
from fplcore.chat.types import ChatCfg, Message, ToolCall, ToolContext, ToolResult, TurnCounters
from fplcore.db.chat_repo import MEMORY_KEYS
from fplcore.rules import IncomingPlayer, SquadSlot


class _NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _ctx() -> ToolContext:
    return ToolContext(
        user_id="user-1",
        entry_id=1,
        season_id="2026/27",
        weights={},
        snapshot_id=1,
        data_version=1,
        now=datetime(2026, 10, 25, tzinfo=UTC),
        has_team=True,
    )


def _players() -> list[NameRecord]:
    return [
        NameRecord(1, "Ødegaard", "Martin", "Ødegaard", "ARS", "MID", 8.5),
        NameRecord(12, "Martinelli", "Gabriel", "Martinelli", "ARS", "MID", 6.8),
        NameRecord(412, "Martinelli", "Alex", "Martinelli", "BRE", "MID", 5.5),
        NameRecord(20, "De Bruyne", "Kevin", "De Bruyne", "MCI", "MID", 9.5),
        NameRecord(30, "Alexander-Arnold", "Trent", "Alexander-Arnold", "LIV", "DEF", 7.2),
    ]


def test_playbook_calls_match_registered_tools() -> None:
    playbooks = SYSTEM_PROMPT.split("# PLAYBOOKS", 1)[1].split("# ANSWER", 1)[0]
    tools = {tool.name: tool for tool in tool_set()}
    for name, args in re.findall(r"\b([a-z][a-z0-9_]*)\(([^)]*)\)", playbooks):
        assert name in tools, name
        fields = set(tools[name].args_model.model_fields)
        for arg in [part.strip() for part in args.split(",") if part.strip()]:
            assert arg in fields, (name, arg)
    mentioned = set(re.findall(r"\b((?:get|evaluate|find|review|resolve|search|compare|explain|save|run)_[a-z0-9_]+)\b", playbooks))
    assert mentioned <= set(tools)
    assert "evaluate_transfer(" not in playbooks
    assert "blanks_doubles" not in playbooks
    assert "get_insights(my_squad" not in playbooks
    assert "explain_topic(chip_advice)" not in playbooks


def test_literal_enums_are_the_registered_values() -> None:
    view = strict_schema(InsightArgs)["properties"]["view"]
    assert "injuries" in view["enum"]
    assert "in_form" in view["enum"]
    kind = strict_schema(MarketArgs)["properties"]["kind"]
    assert "top_in" in kind["enum"]
    assert set(get_args(TopicName)) == set(TOPICS)
    assert set(get_args(PreferenceKey)) == set(MEMORY_KEYS)


async def test_unknown_view_and_kind_are_rejected() -> None:
    registry = ToolRegistry([get_insights, get_market_movers], open_conn=null_connection)
    insight = await registry.execute(
        ToolCall(id="c1", name="get_insights", arguments={"view": "captaincy"}, raw_arguments="{}"),
        _ctx(),
        {},
        TurnCounters(),
    )
    market = await registry.execute(
        ToolCall(id="c2", name="get_market_movers", arguments={"kind": "nope"}, raw_arguments="{}"),
        _ctx(),
        {},
        TurnCounters(),
    )
    assert insight.ok is False and insight.error is not None
    assert insight.error.code == "INVALID_ARGUMENT"
    assert "in_form" in f"{insight.error.message} {insight.error.hint or ''}"
    assert market.ok is False and market.error is not None
    assert market.error.code == "INVALID_ARGUMENT"


def test_names_fold_nicknames_and_ambiguous_surnames() -> None:
    players = _players()
    assert fold("Ødegaard") == fold("Odegaard")
    assert match_query("Odegaard", players)[0].player_id == 1
    assert match_query("KDB", players)[0].player_id == 20
    assert match_query("Trent", players)[0].player_id == 30
    found = mentioned_in("Is Odegaard or KDB better, or Martinelli?", players)
    assert found.resolved[1] == "Ødegaard"
    assert found.resolved[20] == "De Bruyne"
    assert 12 not in found.resolved
    assert 'AMBIGUOUS "Martinelli"' in found.line
    updated = insert_mentioned("<context>\nSQUAD\n</context>", found.line)
    assert updated.endswith(found.line + "\n</context>")


def test_prefetch_runs_only_a_single_read() -> None:
    assert prefetch_tool("Who should I captain?") == "get_captain_options"
    assert prefetch_tool("Sort my bench") == "get_best_lineup"
    assert prefetch_tool("Should I wildcard?") == "get_plan_suggestions"
    assert prefetch_tool("Rate my team") == "review_my_squad"
    assert prefetch_tool("Should I play a chip?") == "get_plan_suggestions"
    assert prefetch_tool("Captain and bench?") is None
    assert prefetch_tool("Is Saka for Palmer worth a hit?") is None
    assert prefetch_tool("When is the deadline?") is None
    assert prefetch_tool("How does the Bench Boost work?") is None
    assert prefetch_tool("How does Triple Captain work?") is None


def test_quote_transfers_prices_the_hit_and_keeps_an_illegal_move_off_the_bank() -> None:
    legal = quote_transfers(
        [SquadSlot(1, 3, 1, 50)],
        [MoveInput(1, IncomingPlayer(2, 3, 2, 55, True), "A", "B", 4.0, 6.4)],
        bank=20,
        free_transfers=1,
        horizon=1,
    )
    assert legal.verdict == "worth_it"
    assert legal.total_delta == 2.4
    assert legal.hits == 0
    assert legal.bank_after == 15

    hit = quote_transfers(
        [SquadSlot(1, 3, 1, 40), SquadSlot(2, 4, 2, 40)],
        [
            MoveInput(1, IncomingPlayer(3, 3, 3, 40, True), "A", "C", 3.0, 5.0),
            MoveInput(2, IncomingPlayer(4, 4, 4, 40, True), "B", "D", 3.0, 5.2),
        ],
        bank=0,
        free_transfers=1,
        horizon=3,
    )
    assert hit.hits == 1
    assert hit.hit_cost == 4
    assert hit.total_delta == 4.2
    assert hit.verdict == "marginal"

    clear = quote_transfers(
        [SquadSlot(1, 3, 1, 40), SquadSlot(2, 4, 2, 40)],
        [
            MoveInput(1, IncomingPlayer(3, 3, 3, 40, True), "A", "C", 3.0, 6.0),
            MoveInput(2, IncomingPlayer(4, 4, 4, 40, True), "B", "D", 3.0, 6.0),
        ],
        bank=0,
        free_transfers=1,
        horizon=3,
    )
    assert clear.total_delta == 6.0
    assert clear.verdict == "worth_it"

    mixed = quote_transfers(
        [SquadSlot(1, 3, 1, 10), SquadSlot(2, 4, 2, 40)],
        [
            MoveInput(1, IncomingPlayer(3, 3, 3, 50, True), "A", "C", 1.0, 2.0),
            MoveInput(2, IncomingPlayer(4, 4, 4, 10, True), "B", "D", 1.0, 3.0),
        ],
        bank=0,
        free_transfers=1,
        horizon=1,
    )
    assert mixed.moves[0].legal is False
    assert mixed.moves[1].legal is True
    assert mixed.verdict == "not_worth_it"
    assert mixed.bank_after == 30


def test_rank_replacements_respects_budget_and_club_limit() -> None:
    outgoing = SquadSlot(1, 3, 1, 50)
    cheap = Candidate(2, "B", 9, "CHE", 3, 40, 9.0, 1.0, "a", True)
    short = rank_replacements(1, [outgoing], [cheap], out_proj=4.0, bank=20, max_price_tenths=None, limit=5)
    assert short.budget_tenths == 70
    assert short.note == "Fewer than 5 are affordable."
    assert short.ranked[0].delta == 5.0

    full_club = [
        outgoing,
        SquadSlot(10, 4, 2, 40),
        SquadSlot(11, 4, 2, 40),
        SquadSlot(12, 4, 2, 40),
    ]
    blocked = Candidate(8, "C", 2, "CHE", 3, 40, 9.0, 1.0, "a", True)
    club = rank_replacements(1, full_club, [blocked], out_proj=4.0, bank=20, max_price_tenths=None, limit=5)
    assert club.ranked == []

    over = Candidate(9, "D", 8, "MCI", 3, 80, 12.0, 1.0, "a", True)
    capped = rank_replacements(1, [outgoing], [over], out_proj=4.0, bank=20, max_price_tenths=60, limit=5)
    assert capped.ranked == []


def test_saved_plan_keeps_the_largest_metric_deltas_and_chip_week() -> None:
    shaped = shape_saved_plan(
        {
            "horizon": 3,
            "hits": 1,
            "gain_vs_roll": 2.5,
            "explanation": "Because.",
            "plan": {
                "headline": "Sell A, buy B",
                "transfers": [
                    {
                        "out": 1,
                        "in": 2,
                        "out_name": "A",
                        "in_name": "B",
                        "cost_delta": 5,
                        "metric_deltas": {"fixture": 0.2, "xgi": 0.01, "form": 0.4},
                    }
                ],
                "captain": {"id": 9},
                "vice": {"id": 8},
                "xi": [{"id": 9}],
                "bench": [{"id": 8}],
                "projected_points_by_gw": {"1": 40},
                "bank_after": 15,
            },
            "alternatives": [{"hits": 0, "transfers": [], "projected_points_by_gw": {"1": 38.0}, "gain_vs_roll": 0}],
            "chip_advice": [
                {"chip": "wildcard", "recommend": "consider_gw_12", "expected_gain": 6.5, "expires_soon": False}
            ],
            "reason_codes": ["FIXTURE_SWING"],
        }
    )
    deltas = shaped["transfers"][0]["metric_deltas"]
    assert set(deltas) == {"form", "fixture"}
    assert shaped["chip_advice"][0]["best_gw"] == 12
    assert shaped["bank_after_m"] == 1.5
    assert shaped["alternatives"][0]["projected_total"] == 38.0
    assert shaped["captain_id"] == 9


def test_ticker_marks_blanks_and_sorts_by_ease() -> None:
    teams = [
        {"id": 1, "short_name": "ARS"},
        {"id": 2, "short_name": "CHE"},
        {"id": 3, "short_name": "MCI"},
    ]
    fixtures = [
        {
            "event": 9,
            "team_h": 1,
            "team_a": 3,
            "team_h_difficulty": 2,
            "team_a_difficulty": 4,
            "home_short": "ARS",
            "away_short": "MCI",
        }
    ]
    ticker = build_ticker(teams, fixtures, [9])
    assert ticker["blanks"]["9"] == ["CHE"]
    assert ticker["doubles"] == {}
    assert [club["team"] for club in ticker["clubs"]] == ["ARS", "MCI", "CHE"]


def test_ranked_players_queries_once_for_a_turn(monkeypatch: Any) -> None:
    calls: list[int | None] = []

    def fake(conn: object, **kwargs: object) -> list[dict[str, object]]:
        del conn
        calls.append(kwargs.get("position"))  # type: ignore[arg-type]
        return [
            {"id": 1, "position_id": 4, "team_id": 2, "now_cost": 100, "proj": 5.0},
            {"id": 2, "position_id": 3, "team_id": 2, "now_cost": 80, "proj": 4.0},
        ]

    monkeypatch.setattr("api.services._ranked_query", fake)
    token = activate_cache(TurnCache(data_version=4))
    try:
        forwards = ranked_players(None, weights={"form": 1.0}, position=4, horizon=1)  # type: ignore[arg-type]
        mids = ranked_players(None, weights={"form": 1.0}, position=3, horizon=1)  # type: ignore[arg-type]
    finally:
        reset_cache(token)
    assert calls == [None]
    assert [row["id"] for row in forwards] == [1]
    assert [row["id"] for row in mids] == [2]


async def test_captain_question_prefetches_before_the_model() -> None:
    seen: list[BaseModel] = []

    def handler(ctx: ToolContext, args: BaseModel, conn: object) -> ToolResult:
        del ctx, conn
        seen.append(args)
        return ToolResult(ok=True, data={"options": [{"id": 1, "name": "Saka", "proj": 6.0}]})

    tool = BoundTool("get_captain_options", "Captain.", _NoArgs, handler)
    events: list[object] = []
    async for event in run_turn(
        [Message(role="user", content="Who should I captain?")],
        llm=ScriptedLlm([text_turn("Captain Saka projects 6.0 points.")]),
        tools=ToolRegistry([tool], open_conn=null_connection),
        cfg=ChatCfg(max_rounds=4, max_tool_calls=6, turn_timeout_s=30),
        ctx=_ctx(),
        context=ContextView(decision_gw=9),
    ):
        events.append(event)
    final = events[-1]
    assert isinstance(final, LoopFinished)
    assert len(seen) == 1
    assert final.tool_call_count == 1
    assert final.rounds == 1
    assert final.grounding == "ok"
