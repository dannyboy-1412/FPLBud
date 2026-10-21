from types import SimpleNamespace

import pytest

from api import services
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import get_suggested_lineup, save_suggested_lineup
from fplcore.lineup import SuggestedLineup, lineup_cache_hash
from fplcore.optimise import PlayerOpt
from fplcore.settings import Settings

LEGAL = {
    "starters": [1, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14],
    "bench": [2, 7, 12, 15],
    "captain_id": 13,
    "vice_id": 8,
    "summary": "Keep the penalty taker on the pitch.",
    "source": "llm",
}


class _Result:
    def __init__(self, row: dict | None) -> None:
        self._row = row

    def fetchone(self) -> dict | None:
        return self._row


class _Conn:
    def __init__(self, row: dict | None = None, *, weights: dict | None = None) -> None:
        self.statements: list[tuple[str, list | None]] = []
        self.row = row
        self.weights = weights
        self.commits = 0

    def execute(self, sql: str, params: list | None = None) -> _Result:
        self.statements.append((" ".join(sql.split()), list(params) if params is not None else None))
        if self.weights is not None or "profiles" in sql:
            return _Result({"fpl_entry_id": 42, "weights": self.weights})
        return _Result(self.row)

    def commit(self) -> None:
        self.commits += 1


def _squad() -> tuple[list[PlayerOpt], list[dict]]:
    players: list[PlayerOpt] = []
    squad: list[dict] = []
    player_id = 1
    for position, count in [(1, 2), (2, 5), (3, 5), (4, 3)]:
        for _ in range(count):
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
                    proj=[float(player_id), 1.0],
                    scores_gw1={"form": 0.5},
                )
            )
            squad.append(
                {
                    "element": player_id,
                    "team_id": (player_id % 5) + 1,
                    "position_id": position,
                    "squad_position": player_id,
                    "web_name": f"P{player_id}",
                    "now_cost": 50,
                    "status": "a",
                    "news": "",
                }
            )
            player_id += 1
    return players, squad


def _snapshot(squad: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(season_id="2026/27", squad_players=squad)


def _wire(monkeypatch: pytest.MonkeyPatch, players: list[PlayerOpt], squad: list[dict]) -> dict:
    box: dict[tuple, dict] = {}
    seen = {"choose": 0, "cap": 0, "allow": None, "get": None}

    async def load(conn: object, client: object, entry_id: int) -> tuple[dict, SimpleNamespace]:
        assert entry_id == 42
        return {}, SimpleNamespace(teams=[])

    def get(conn: object, user_id: object, entry_id: int, gameweek: int, squad_hash: str) -> dict | None:
        seen["get"] = (user_id, entry_id, gameweek, squad_hash)
        return box.get((user_id, entry_id, gameweek, squad_hash))

    def save(conn: object, *, user_id: object, entry_id: int, gameweek: int, squad_hash: str, lineup: dict) -> None:
        box[(user_id, entry_id, gameweek, squad_hash)] = lineup

    async def choose(
        players_in: list[PlayerOpt],
        dossier: list,
        *,
        settings: Settings,
        allow_llm: bool,
        client: object = None,
    ) -> SuggestedLineup:
        seen["choose"] += 1
        seen["allow"] = allow_llm
        return SuggestedLineup(**LEGAL)

    def cap(conn: object, limit: int) -> bool:
        seen["cap"] += 1
        return True

    monkeypatch.setattr(services, "load_merged_entry", load)
    monkeypatch.setattr(services, "snapshot_from_cache", lambda *args, **kwargs: _snapshot(squad))
    monkeypatch.setattr(services, "current_season_id", lambda conn: "2026/27")
    monkeypatch.setattr(services, "_squad_opts", lambda conn, snapshot, weights: players)
    monkeypatch.setattr(services.stats_repo, "next_gw_id", lambda conn, season_id: 12)
    monkeypatch.setattr(services.stats_repo, "next_event_fixtures", lambda conn: {})
    monkeypatch.setattr(services, "get_suggested_lineup", get)
    monkeypatch.setattr(services, "save_suggested_lineup", save)
    monkeypatch.setattr(services, "choose_lineup", choose)
    monkeypatch.setattr(services, "try_llm_cap", cap)
    return seen


def _settings(**overrides: object) -> Settings:
    values = {
        "llm_enabled": False,
        "llm_api_key": "test-key",
        "llm_model": "test/model",
        "llm_daily_call_cap": 200,
    }
    values.update(overrides)
    return Settings(**values)


async def test_cached_lineup_skips_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    players, squad = _squad()
    seen = _wire(monkeypatch, players, squad)
    weights = {"form": 0.4, "fixture": 0.6}
    conn = _Conn(weights=weights)
    first = await services.build_suggested_xi(conn, _settings(), "user-1")
    second = await services.build_suggested_xi(conn, _settings(), "user-1")

    assert first == LEGAL
    assert second == LEGAL
    assert seen["choose"] == 1
    assert seen["cap"] == 1
    assert seen["allow"] is True
    assert conn.commits == 2
    user_id, entry_id, gameweek, squad_hash = seen["get"]
    assert (user_id, entry_id, gameweek) == ("user-1", 42, 12)
    assert squad_hash == lineup_cache_hash([player["element"] for player in squad], weights)


async def test_weight_change_is_a_new_lineup(monkeypatch: pytest.MonkeyPatch) -> None:
    players, squad = _squad()
    seen = _wire(monkeypatch, players, squad)
    conn = _Conn(weights={"form": 0.2})
    await services.build_suggested_xi(conn, _settings(), "user-1")
    conn.weights = {"form": 0.9}
    await services.build_suggested_xi(conn, _settings(), "user-1")
    assert seen["choose"] == 2
    assert seen["cap"] == 2


async def test_daily_cap_stores_projected_xi(monkeypatch: pytest.MonkeyPatch) -> None:
    players, squad = _squad()
    original_choose = services.choose_lineup
    _wire(monkeypatch, players, squad)
    monkeypatch.setattr(services, "choose_lineup", original_choose)
    monkeypatch.setattr(services, "try_llm_cap", lambda conn, limit: False)
    seen: dict[str, str] = {}

    def get(conn: object, user_id: object, entry_id: int, gameweek: int, squad_hash: str) -> None:
        seen["hash"] = squad_hash
        return None

    stored: dict = {}

    def save(conn: object, *, user_id: object, entry_id: int, gameweek: int, squad_hash: str, lineup: dict) -> None:
        stored.update(lineup)

    monkeypatch.setattr(services, "get_suggested_lineup", get)
    monkeypatch.setattr(services, "save_suggested_lineup", save)
    conn = _Conn(weights=None)
    result = await services.build_suggested_xi(conn, _settings(llm_enabled=True), "user-1")
    assert result["source"] == "optimiser"
    assert "projected points" in result["summary"]
    assert stored == result
    assert result["captain_id"] in result["starters"]
    assert result["captain_id"] != result["vice_id"]
    assert seen["hash"] == lineup_cache_hash([player["element"] for player in squad], DEFAULT_WEIGHTS)
    assert conn.commits == 1


async def test_missing_model_does_not_spend_the_daily_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    players, squad = _squad()
    seen = _wire(monkeypatch, players, squad)
    conn = _Conn(weights={"form": 1})
    await services.build_suggested_xi(conn, _settings(llm_api_key="", llm_model=""), "user-1")
    assert seen["cap"] == 0
    assert seen["allow"] is False
    assert seen["choose"] == 1


def test_suggested_lineup_round_trip_uses_the_full_key() -> None:
    conn = _Conn(row={"lineup": LEGAL})
    found = get_suggested_lineup(conn, "user-1", 42, 12, "abc")
    sql, params = conn.statements[0]
    assert "from suggested_lineups" in sql
    assert params == ["user-1", 42, 12, "abc"]
    assert found == LEGAL

    save_suggested_lineup(conn, user_id="user-1", entry_id=42, gameweek=12, squad_hash="abc", lineup=LEGAL)
    insert, values = conn.statements[1]
    assert "insert into suggested_lineups" in insert
    assert "on conflict (user_id, entry_id, gameweek, squad_hash)" in insert
    assert values[:4] == ["user-1", 42, 12, "abc"]


def test_non_object_lineup_is_a_miss() -> None:
    conn = _Conn(row={"lineup": "[1, 2]"})
    assert get_suggested_lineup(conn, "user-1", 42, 12, "abc") is None
