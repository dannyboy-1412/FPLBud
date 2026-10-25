import pytest

from fplcore.constants import SQUAD_MAX_PLAY, SQUAD_MIN_PLAY
from fplcore.lineup import (
    LineupRejected,
    choose_lineup,
    lineup_cache_hash,
    lineup_from_optimiser,
    unused_starter_reasons,
    validate_lineup,
)
from fplcore.llm import LlmError
from fplcore.optimise import PlayerOpt
from fplcore.settings import Settings


def _positions() -> dict[int, int]:
    positions: dict[int, int] = {}
    player_id = 1
    for position, count in [(1, 2), (2, 5), (3, 5), (4, 3)]:
        for _ in range(count):
            positions[player_id] = position
            player_id += 1
    return positions


def _legal() -> dict:
    return {
        "starters": [1, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14],
        "bench": [2, 7, 12, 15],
        "captain_id": 13,
        "vice_id": 8,
        "summary": "Keep the penalty taker on the pitch.",
    }


def test_legal_lineup_passes() -> None:
    lineup = validate_lineup(_legal(), _positions())
    assert lineup.source == "llm"
    assert len(lineup.starters) == 11
    assert lineup.captain_id == 13
    assert lineup.vice_id == 8
    assert lineup.bench[0] == 2
    assert lineup.summary.startswith("Keep")


def test_two_defenders_rejected() -> None:
    payload = _legal()
    payload["starters"] = [1, 3, 4, 8, 9, 10, 11, 12, 13, 14, 15]
    payload["bench"] = [2, 5, 6, 7]
    with pytest.raises(LineupRejected, match="DEF"):
        validate_lineup(payload, _positions())


def test_player_outside_squad_rejected() -> None:
    payload = _legal()
    payload["starters"] = [99, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14]
    with pytest.raises(LineupRejected, match="outside"):
        validate_lineup(payload, _positions())


def test_benched_captain_rejected() -> None:
    payload = _legal()
    payload["captain_id"] = 2
    with pytest.raises(LineupRejected, match="captain must start"):
        validate_lineup(payload, _positions())


def test_duplicated_vice_rejected() -> None:
    payload = _legal()
    payload["vice_id"] = payload["captain_id"]
    with pytest.raises(LineupRejected, match="different"):
        validate_lineup(payload, _positions())


def _fifteen() -> list[PlayerOpt]:
    players: list[PlayerOpt] = []
    player_id = 1
    for position, count in [(1, 2), (2, 5), (3, 5), (4, 3)]:
        for slot in range(count):
            players.append(
                PlayerOpt(
                    id=player_id,
                    web_name=f"P{player_id}",
                    team_id=(player_id % 5) + 1,
                    position_id=position,
                    cost=50,
                    sell=50,
                    in_squad=True,
                    can_in=False,
                    locked=True,
                    proj=[float(slot + 1), 1.0],
                    scores_gw1={"form": 0.5},
                )
            )
            player_id += 1
    return players


def test_optimiser_fallback_is_a_legal_xi() -> None:
    players = _fifteen()
    lineup = lineup_from_optimiser(players)
    positions = {player.id: player.position_id for player in players}
    assert lineup.source == "optimiser"
    assert len(lineup.starters) == 11
    assert lineup.captain_id in lineup.starters
    assert lineup.vice_id in lineup.starters
    assert lineup.captain_id != lineup.vice_id
    assert positions[lineup.bench[0]] == 1
    counts: dict[int, int] = {}
    for player_id in lineup.starters:
        counts[positions[player_id]] = counts.get(positions[player_id], 0) + 1
    for position, minimum in SQUAD_MIN_PLAY.items():
        assert counts[position] >= minimum
    for position, maximum in SQUAD_MAX_PLAY.items():
        assert counts[position] <= maximum
    assert set(lineup.starters) | set(lineup.bench) == set(positions)


def test_lineup_cache_hash_tracks_squad_and_weights_only() -> None:
    weights = {"fixture": 0.25, "form": 0.3}
    reordered = {"form": 0.3, "fixture": 0.25}
    assert lineup_cache_hash([3, 1, 2], weights) == lineup_cache_hash([1, 2, 3], reordered)
    assert lineup_cache_hash([1, 2, 3], weights) != lineup_cache_hash([1, 2, 4], weights)
    assert lineup_cache_hash([1, 2, 3], weights) != lineup_cache_hash([1, 2, 3], {**weights, "form": 0.4})


class _Model:
    def __init__(self, first: dict | Exception, repair: dict | Exception | None = None) -> None:
        self.first = first
        self.repair = repair
        self.searches = 0
        self.repairs = 0

    async def chat_with_search(self, *, system: str, user: str) -> dict:
        self.searches += 1
        if isinstance(self.first, Exception):
            raise self.first
        return self.first

    async def chat_json(self, *, system: str, user: str) -> dict:
        self.repairs += 1
        assert "Do not search" in user
        if isinstance(self.repair, Exception):
            raise self.repair
        return self.repair or {}


def _settings(*, key: str = "test-key", model: str = "test/model") -> Settings:
    return Settings(llm_enabled=False, llm_api_key=key, llm_model=model, llm_daily_call_cap=200)


async def test_model_lineup_is_kept_when_it_is_legal() -> None:
    model = _Model(_legal())
    lineup = await choose_lineup(_fifteen(), [], settings=_settings(), allow_llm=True, client=model)
    assert lineup.source == "llm"
    assert lineup.captain_id == 13
    assert model.searches == 1
    assert model.repairs == 0


async def test_repair_is_accepted_when_legal() -> None:
    model = _Model({"starters": [99], "bench": [], "captain_id": 1, "vice_id": 2, "summary": "no"}, _legal())
    lineup = await choose_lineup(_fifteen(), [], settings=_settings(), allow_llm=True, client=model)
    assert lineup.source == "llm"
    assert lineup.captain_id == 13
    assert model.searches == 1
    assert model.repairs == 1


async def test_one_repair_then_projected_xi() -> None:
    model = _Model({"starters": [99], "bench": [], "captain_id": 1, "vice_id": 2, "summary": "no"}, {"starters": []})
    lineup = await choose_lineup(_fifteen(), [], settings=_settings(), allow_llm=True, client=model)
    assert lineup.source == "optimiser"
    assert "projected points" in lineup.summary
    assert model.searches == 1
    assert model.repairs == 1


async def test_search_failure_skips_repair() -> None:
    model = _Model(LlmError("timeout"))
    lineup = await choose_lineup(_fifteen(), [], settings=_settings(), allow_llm=True, client=model)
    assert lineup.source == "optimiser"
    assert model.searches == 1
    assert model.repairs == 0


def _keepers() -> list[dict]:
    return [
        {
            "id": 1,
            "name": "Wright",
            "position": "GKP",
            "minutes": 0,
            "status": "a",
            "chance_of_playing_next_round": 100,
        },
        {
            "id": 2,
            "name": "Raya",
            "position": "GKP",
            "minutes": 720,
            "status": "a",
            "chance_of_playing_next_round": 100,
        },
    ]


def test_unused_goalkeeper_is_not_a_valid_start() -> None:
    reasons = unused_starter_reasons(_legal()["starters"], _keepers())
    assert reasons
    assert "Wright" in reasons[0]
    assert "Raya" in reasons[0]


async def test_model_that_starts_an_unused_goalkeeper_is_replaced() -> None:
    played = _legal()
    played["starters"] = [2, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14]
    played["bench"] = [1, 7, 12, 15]
    model = _Model(_legal(), played)
    lineup = await choose_lineup(
        _fifteen(), _keepers(), settings=_settings(), allow_llm=True, client=model
    )
    assert lineup.source == "llm"
    assert 2 in lineup.starters
    assert 1 in lineup.bench
    assert model.repairs == 1


async def test_repeated_unused_goalkeeper_falls_back_to_projection() -> None:
    model = _Model(_legal(), _legal())
    lineup = await choose_lineup(
        _fifteen(), _keepers(), settings=_settings(), allow_llm=True, client=model
    )
    assert lineup.source == "optimiser"
    assert 2 in lineup.starters
    assert 1 in lineup.bench


async def test_missing_model_config_uses_projected_xi() -> None:
    model = _Model(_legal())
    lineup = await choose_lineup(_fifteen(), [], settings=_settings(key="", model=""), allow_llm=True, client=model)
    assert lineup.source == "optimiser"
    assert model.searches == 0
