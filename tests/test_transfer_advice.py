import json

import pandas as pd
import pytest

from fplcore.llm import LlmError
from fplcore.optimise import PlayerOpt, SolvedPlan, TransferMove
from fplcore.settings import Settings
from fplcore.transfer_advice import (
    advice_from_model,
    advice_from_plans,
    choose_transfers,
    fixture_run,
    option_cost,
    stored_advice_ok,
    transfer_cache_hash,
)


def _move(out_id: int, in_id: int, out_name: str = "Out", in_name: str = "In") -> TransferMove:
    return TransferMove(out_id, in_id, out_name, in_name, 0, {})


def _plan(
    count: int,
    objective: float,
    moves: list[TransferMove] | None = None,
    xi: list[int] | None = None,
) -> SolvedPlan:
    xi_ids = xi or list(range(1, 12))
    return SolvedPlan(
        transfers_in=count,
        hits=0,
        objective=objective,
        projected_gw1=objective,
        squad_ids=list(range(1, 16)),
        xi_ids=xi_ids,
        bench_ids=[12, 13, 14, 15],
        captain_id=xi_ids[0],
        vice_id=xi_ids[1],
        bank_after=10,
        moves=moves or [],
    )


def _advise(plans: dict[int, SolvedPlan], free_transfers: int, absent: set[int] | None = None, names: dict[int, str] | None = None):
    return advice_from_plans(
        plans,
        free_transfers=free_transfers,
        unavailable_ids=absent or set(),
        names=names,
    )


def test_option_cost_is_highest_for_the_last_transfer() -> None:
    assert option_cost(1, 1) == 2.5
    assert option_cost(2, 1) == 1.5
    assert option_cost(2, 2) == 4.0
    assert option_cost(5, 1) == 1.0
    assert option_cost(5, 3) == 3.0
    assert option_cost(5, 5) == 7.0


def test_one_free_transfer_rolls_a_marginal_move() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 12.4, [_move(1, 99)])}, 1)
    assert advice.action == "roll"
    assert advice.moves == []
    assert advice.summary == (
        "Roll the free transfer. No move is clear enough, and banking it leaves two next week."
    )


def test_one_free_transfer_is_spent_when_the_move_is_clear() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 12.6, [_move(1, 99, "Watkins", "Haaland")])}, 1)
    assert advice.action == "transfer"
    assert [(move.out_id, move.in_id) for move in advice.moves] == [(1, 99)]
    assert advice.summary == "Sell Watkins for Haaland. That uses the free transfer."


def test_a_tie_with_rolling_keeps_the_transfer() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 12.5, [_move(1, 99)])}, 1)
    assert advice.action == "roll"


def test_two_free_transfers_bank_the_second_when_it_is_not_clear() -> None:
    plans = {
        0: _plan(0, 10),
        1: _plan(1, 12.0, [_move(1, 99, "Watkins", "Haaland")]),
        2: _plan(2, 14.0, [_move(1, 99, "Watkins", "Haaland"), _move(2, 98, "Cash", "Gabriel")]),
    }
    advice = _advise(plans, 2)
    assert advice.action == "transfer"
    assert len(advice.moves) == 1
    assert advice.summary == "Sell Watkins for Haaland. One free transfer stays in the bank."


def test_two_clear_moves_use_both_free_transfers() -> None:
    plans = {
        0: _plan(0, 10),
        1: _plan(1, 12.0, [_move(1, 99, "Watkins", "Haaland")]),
        2: _plan(2, 14.6, [_move(1, 99, "Watkins", "Haaland"), _move(2, 98, "Cash", "Gabriel")]),
    }
    advice = _advise(plans, 2)
    assert len(advice.moves) == 2
    assert advice.summary == "Use both free transfers: sell Watkins for Haaland and sell Cash for Gabriel."


def test_a_spare_transfer_near_the_cap_is_cheaper_to_spend() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 11.2, [_move(1, 99, "Cash", "Gabriel")])}, 4)
    assert advice.action == "transfer"
    assert advice.summary == "Sell Cash for Gabriel. Three free transfers stay in the bank."


def test_a_sideways_move_still_rolls_at_five_free_transfers() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 10.8, [_move(1, 99)])}, 5)
    assert advice.action == "roll"
    assert advice.summary == "Roll all 5 free transfers. No move is a clear upgrade."


def test_an_absent_starter_is_sold_even_when_the_gain_is_small() -> None:
    roll = _plan(0, 10)
    sale = _plan(1, 10.1, [_move(5, 99, "Saka", "Gordon")])
    advice = _advise({0: roll, 1: sale}, 1, absent={5}, names={5: "Saka"})
    assert advice.action == "transfer"
    assert advice.moves[0].out_name == "Saka"
    assert advice.summary == "Saka is out, so sell Saka for Gordon. That uses the free transfer."


def test_an_absent_player_on_the_bench_does_not_force_a_transfer() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 10.1, [_move(12, 99)])}, 1, absent={12})
    assert advice.action == "roll"
    assert "out" not in advice.summary


def test_roll_names_an_absent_starter_when_no_replacement_holds_up() -> None:
    roll = _plan(0, 10)
    sale = _plan(1, 7.0, [_move(5, 99, "Saka", "Gordon")])
    advice = _advise({0: roll, 1: sale}, 1, absent={5, 6}, names={5: "Saka", 6: "White"})
    assert advice.action == "roll"
    assert advice.summary == "Roll. Saka and White are out, and no replacement is a clear upgrade."


def test_hits_are_not_suggested() -> None:
    hit = _plan(1, 40, [_move(1, 99)])
    hit.hits = 1
    advice = _advise({0: _plan(0, 10), 1: hit}, 1)
    assert advice.action == "roll"


def test_no_free_transfer_rolls() -> None:
    advice = _advise({0: _plan(0, 10)}, 0)
    assert advice.summary == "No free transfer this week, so roll."


def test_cache_hash_changes_with_bank_transfers_and_selling_price() -> None:
    base = transfer_cache_hash([1, 2], {"form": 0.3}, 1, 5, {"1": 50})
    assert base == transfer_cache_hash([2, 1], {"form": 0.3}, 1, 5, {1: 50})
    assert base != transfer_cache_hash([1, 2], {"form": 0.3}, 2, 5, {"1": 50})
    assert base != transfer_cache_hash([1, 2], {"form": 0.3}, 1, 15, {"1": 50})
    assert base != transfer_cache_hash([1, 2], {"form": 0.3}, 1, 5, {"1": 45})


def _names() -> dict[int, str]:
    return {1: "Out", 99: "In"}


def test_model_can_roll_a_move_the_rules_would_make() -> None:
    plans = {0: _plan(0, 10), 1: _plan(1, 13, [_move(1, 99, "Out", "In")])}
    policy = _advise(plans, 1, names=_names())
    assert policy.action == "transfer"
    advice = advice_from_model(
        {"action": "roll", "moves": [], "summary": "Roll. The target is a doubt."},
        plans,
        policy=policy,
        free_transfers=1,
        unavailable_ids=set(),
        names=_names(),
    )
    assert advice.action == "roll"
    assert advice.source == "llm"
    assert advice.summary == "Roll. The target is a doubt."
    chosen = next(option for option in advice.options if option["chosen"])
    assert "doubt" in chosen["reason"]
    assert any(option["action"] == "transfer" for option in advice.options)


def test_model_cannot_pick_a_move_that_is_not_an_alternative() -> None:
    plans = {0: _plan(0, 10), 1: _plan(1, 13, [_move(1, 99, "Out", "In")])}
    policy = _advise(plans, 1, names=_names())
    with pytest.raises(Exception, match="alternatives"):
        advice_from_model(
            {"action": "transfer", "moves": [{"out_id": 2, "in_id": 50}], "summary": "Sell someone else."},
            plans,
            policy=policy,
            free_transfers=1,
            unavailable_ids=set(),
            names=_names(),
        )


def _roll_payload(free_transfers: int) -> dict:
    return {
        "action": "roll",
        "free_transfers": free_transfers,
        "moves": [],
        "incomings": [],
        "summary": "Roll.",
        "source": "policy",
        "options": [
            {
                "action": "roll",
                "moves": [],
                "recommended_pct": 100,
                "reason": "Bank the free transfer.",
                "chosen": True,
                "incomings": [],
            }
        ],
    }


def test_stored_roll_must_match_the_free_transfer_count() -> None:
    squad = set(range(1, 16))
    assert stored_advice_ok(_roll_payload(2), squad, 2)
    assert not stored_advice_ok(_roll_payload(1), squad, 2)
    bare = _roll_payload(2)
    bare["options"] = []
    assert not stored_advice_ok(bare, squad, 2)


def test_options_show_every_move_with_a_share_of_the_recommendation() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 12.4, [_move(1, 99, "Wright", "Kinsky")])}, 1)
    roll = next(option for option in advice.options if option["action"] == "roll")
    move = next(option for option in advice.options if option["action"] == "transfer")
    assert roll["chosen"] is True
    assert roll["recommended_pct"] > move["recommended_pct"]
    assert sum(option["recommended_pct"] for option in advice.options) == 100
    assert "Kinsky" in roll["reason"]
    assert "Wright" in move["reason"]
    assert "starting XI" in move["reason"]


def test_a_wide_gap_still_shows_every_suggestion() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 30, [_move(1, 99, "Wright", "Kinsky")])}, 1)
    move = next(option for option in advice.options if option["action"] == "transfer")
    roll = next(option for option in advice.options if option["action"] == "roll")
    assert move["chosen"] is True
    assert move["recommended_pct"] > roll["recommended_pct"]
    assert roll["recommended_pct"] >= 8
    assert sum(option["recommended_pct"] for option in advice.options) == 100
    assert "Kinsky" in roll["reason"]


def test_model_reasons_drop_citations() -> None:
    plans = {0: _plan(0, 10), 1: _plan(1, 13, [_move(1, 99, "Wright", "Kinsky")])}
    policy = _advise(plans, 1, names={1: "Wright", 99: "Kinsky"})
    advice = advice_from_model(
        {
            "action": "transfer",
            "moves": [{"out_id": 1, "in_id": 99}],
            "summary": (
                "Sell Wright for Kinsky. Wright has not played. "
                "([site.app](https://example.com/wright?utm_source=openai))"
            ),
        },
        plans,
        policy=policy,
        free_transfers=1,
        unavailable_ids=set(),
        names={1: "Wright", 99: "Kinsky"},
    )
    chosen = next(option for option in advice.options if option["chosen"])
    assert "http" not in chosen["reason"]
    assert "site.app" not in chosen["reason"]
    assert "Wright has not played" in chosen["reason"]


def test_one_free_transfer_shows_the_roll_and_two_moves() -> None:
    plans = [
        _plan(0, 10),
        _plan(1, 14, [_move(1, 99, "Manzambi", "Ayari")]),
        _plan(1, 13, [_move(1, 98, "Manzambi", "Rogers")]),
        _plan(1, 11, [_move(2, 97, "Silva", "Mitchell")]),
    ]
    advice = _advise(plans, 1)
    transfers = [option for option in advice.options if option["action"] == "transfer"]
    rolls = [option for option in advice.options if option["action"] == "roll"]
    assert len(rolls) == 1
    assert len(transfers) == 2
    assert sum(option["recommended_pct"] for option in advice.options) == 100
    incoming = {move["in_id"] for option in transfers for move in option["moves"]}
    assert incoming == {99, 98}


def test_a_marginal_move_gives_the_roll_the_largest_share() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 12.4, [_move(1, 99)])}, 1)
    shares = [option["recommended_pct"] for option in advice.options]
    roll = next(option for option in advice.options if option["action"] == "roll")
    assert roll["recommended_pct"] == max(shares)
    assert roll["chosen"] is True


def test_selling_manzambi_for_a_small_gain_rolls() -> None:
    advice = _advise(
        {
            0: _plan(0, 30),
            1: _plan(1, 32.3, [_move(1, 99, "Manzambi", "Ayari")]),
        },
        1,
        names={1: "Manzambi", 99: "Ayari"},
    )
    assert advice.action == "roll"
    chosen = next(option for option in advice.options if option["chosen"])
    assert chosen["action"] == "roll"
    assert chosen["recommended_pct"] > 50
    assert any(option["action"] == "transfer" for option in advice.options)


def test_fixture_run_lists_three_gameweeks_and_a_leaky_opponent() -> None:
    upcoming = [
        {
            "event": event,
            "team_h": opponent,
            "team_a": 1,
            "team_h_difficulty": 3,
            "team_a_difficulty": fdr,
            "home_short": "OPP",
            "away_short": "AVL",
        }
        for event, opponent, fdr in ((10, 2, 4), (11, 3, 2), (12, 4, 2))
    ]
    ratings = pd.DataFrame(
        [
            {"team_id": 2, "xg_for": 0.4, "xg_against": 2.0, "matches": 6},
            {"team_id": 3, "xg_for": 1.2, "xg_against": 1.0, "matches": 6},
            {"team_id": 4, "xg_for": 1.5, "xg_against": 0.8, "matches": 6},
        ]
    )
    run = fixture_run(upcoming, ratings, [10, 11, 12])
    assert [row["gameweek"] for row in run[1]] == [10, 11, 12]
    assert run[1][0]["fdr"] == 4
    assert run[1][0]["is_home"] is False
    assert run[1][0]["opponent_defence"] == 1.0


def test_a_clear_transfer_is_the_majority_recommendation() -> None:
    advice = _advise({0: _plan(0, 10), 1: _plan(1, 13, [_move(1, 99, "Watkins", "Haaland")])}, 1)
    transfer = next(option for option in advice.options if option["chosen"])
    assert transfer["action"] == "transfer"
    assert transfer["recommended_pct"] > 50
    assert "Haaland" in transfer["reason"]


class _Model:
    def __init__(self, first: dict | Exception, repair: dict | Exception | None = None) -> None:
        self.first = first
        self.repair = repair
        self.user = ""
        self.repairs = 0

    async def chat_with_search(self, *, system: str, user: str) -> dict:
        self.user = user
        if isinstance(self.first, Exception):
            raise self.first
        return self.first

    async def chat_json(self, *, system: str, user: str) -> dict:
        self.repairs += 1
        assert "Do not search" in user
        if isinstance(self.repair, Exception):
            raise self.repair
        return self.repair or {}

    async def aclose(self) -> None:
        return None


def _wire(monkeypatch: pytest.MonkeyPatch) -> dict[int, SolvedPlan]:
    plans = {0: _plan(0, 10), 1: _plan(1, 13, [_move(1, 99, "Out", "In")])}

    def solve(*args: object, **kwargs: object) -> dict:
        assert kwargs["horizon"] == 3
        assert kwargs["max_hits"] == 0
        assert kwargs["free_transfers"] == 1
        assert kwargs["alternatives_per_count"] == 3
        return {"all": plans}

    monkeypatch.setattr("fplcore.transfer_advice.optimise_horizon", solve)
    return plans


def _settings() -> Settings:
    return Settings(llm_enabled=False, llm_api_key="test-key", llm_model="test/model", llm_daily_call_cap=200)


async def test_the_model_sees_the_next_three_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    def solve(*args: object, **kwargs: object) -> dict:
        return {"all": {0: _plan(0, 10), 1: _plan(1, 13, [_move(1, 99, "Manzambi", "Ayari")])}}

    monkeypatch.setattr("fplcore.transfer_advice.optimise_horizon", solve)
    player = PlayerOpt(
        id=1,
        web_name="Manzambi",
        team_id=1,
        position_id=3,
        cost=61,
        sell=61,
        in_squad=True,
        can_in=False,
        locked=False,
        proj=[4.0, 4.0, 4.0],
        scores_gw1={},
    )
    model = _Model({"action": "roll", "moves": [], "summary": "Roll."})
    await choose_transfers(
        [player],
        bank=10,
        free_transfers=1,
        squad_notes=[{"id": 1, "status": "a", "chance_of_playing_next_round": 100, "news": "", "minutes": 400}],
        team_names={1: "AVL"},
        fixtures_by_team={
            1: [
                {"gameweek": 10, "opponent": "MUN", "fdr": 4, "is_home": False, "opponent_attack": 0.2, "opponent_defence": 0.9},
                {"gameweek": 11, "opponent": "SUN", "fdr": 2, "is_home": True, "opponent_attack": 0.4, "opponent_defence": 0.5},
                {"gameweek": 12, "opponent": "IPS", "fdr": 2, "is_home": False, "opponent_attack": 0.3, "opponent_defence": 0.7},
            ]
        },
        settings=_settings(),
        allow_llm=True,
        client=model,
    )
    fixtures = json.loads(model.user)["squad"][0]["fixtures"]
    assert [row["gameweek"] for row in fixtures] == [10, 11, 12]
    assert fixtures[0]["opponent_defence"] == 0.9


async def test_rules_decide_when_the_model_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch)
    advice = await choose_transfers(
        [],
        bank=10,
        free_transfers=1,
        squad_notes=[],
        team_names={},
        fixtures_by_team={},
        settings=Settings(llm_api_key="", llm_model=""),
        allow_llm=True,
    )
    assert advice.source == "policy"
    assert advice.action == "transfer"
    assert advice.moves[0].in_name == "In"


async def test_model_roll_is_kept_and_a_weak_alternative_is_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    def solve(*args: object, **kwargs: object) -> dict:
        return {
            "all": {
                0: _plan(0, 10),
                1: _plan(1, 12.0, [_move(1, 99, "Watkins", "Haaland")]),
                2: _plan(2, 13.0, [_move(1, 99, "Watkins", "Haaland"), _move(2, 98, "Cash", "Gabriel")]),
            }
        }

    monkeypatch.setattr("fplcore.transfer_advice.optimise_horizon", solve)
    model = _Model({"action": "roll", "moves": [], "summary": "Roll. Wait for the press conferences."})
    advice = await choose_transfers(
        [],
        bank=10,
        free_transfers=2,
        squad_notes=[{"id": 1, "status": "a", "chance_of_playing_next_round": 100, "news": "", "minutes": 900}],
        team_names={1: "AVL"},
        fixtures_by_team={},
        settings=_settings(),
        allow_llm=True,
        client=model,
    )
    counts = [item["transfers"] for item in json.loads(model.user)["alternatives"]]
    assert 2 not in counts
    assert advice.action == "roll"
    assert advice.source == "llm"
    assert "press conferences" in advice.summary


async def test_rejected_model_plan_falls_back_to_the_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch)
    model = _Model(
        {"action": "transfer", "moves": [{"out_id": 4, "in_id": 70}], "summary": "No."},
        {"action": "transfer", "moves": [{"out_id": 4, "in_id": 71}], "summary": "Still no."},
    )
    advice = await choose_transfers(
        [],
        bank=10,
        free_transfers=1,
        squad_notes=[],
        team_names={},
        fixtures_by_team={},
        settings=_settings(),
        allow_llm=True,
        client=model,
    )
    assert advice.source == "policy"
    assert advice.action == "transfer"
    assert model.repairs == 1


async def test_search_failure_uses_the_rules_without_a_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch)
    model = _Model(LlmError("timeout"))
    advice = await choose_transfers(
        [],
        bank=0,
        free_transfers=1,
        squad_notes=[],
        team_names={},
        fixtures_by_team={},
        settings=_settings(),
        allow_llm=True,
        client=model,
    )
    assert advice.source == "policy"
    assert model.repairs == 0
