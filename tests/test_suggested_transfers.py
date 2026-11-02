from types import SimpleNamespace

import pytest

from api import services
from fplcore.db.repos import get_suggested_transfers, save_suggested_transfers
from fplcore.settings import Settings
from fplcore.transfer_advice import TransferSuggestion, transfer_cache_hash


class _Result:
    def __init__(self, row: dict | None) -> None:
        self._row = row

    def fetchone(self) -> dict | None:
        return self._row


class _Conn:
    def __init__(self, *, weights: dict | None) -> None:
        self.statements: list[tuple[str, list | None]] = []
        self.weights = weights
        self.commits = 0

    def execute(self, sql: str, params: list | None = None) -> _Result:
        self.statements.append((" ".join(sql.split()), list(params) if params is not None else None))
        return _Result({"fpl_entry_id": 42, "weights": self.weights})

    def commit(self) -> None:
        self.commits += 1


def _squad() -> list[dict]:
    squad: list[dict] = []
    player_id = 1
    for position, count in [(1, 2), (2, 5), (3, 5), (4, 3)]:
        for _ in range(count):
            squad.append(
                {
                    "element": player_id,
                    "team_id": (player_id % 5) + 1,
                    "position_id": position,
                    "web_name": f"P{player_id}",
                    "now_cost": 50,
                    "status": "a",
                    "news": "",
                    "minutes": 90,
                }
            )
            player_id += 1
    return squad


def _snapshot(squad: list[dict], *, free_transfers: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        season_id="2026/27",
        squad_players=squad,
        free_transfers=free_transfers,
        bank=15,
        selling_prices={str(player["element"]): 50 for player in squad},
    )


def _wire(monkeypatch: pytest.MonkeyPatch, squad: list[dict]) -> dict:
    box: dict[tuple, dict] = {}
    seen = {"choose": 0, "cap": 0, "allow": None, "ft": None}

    async def load(conn: object, client: object, entry_id: int) -> tuple[dict, SimpleNamespace]:
        assert entry_id == 42
        return {}, SimpleNamespace(teams=[])

    def get(conn: object, user_id: object, entry_id: int, gameweek: int, squad_hash: str) -> dict | None:
        return box.get((user_id, entry_id, gameweek, squad_hash))

    def save(conn: object, *, user_id: object, entry_id: int, gameweek: int, squad_hash: str, advice: dict) -> None:
        box[(user_id, entry_id, gameweek, squad_hash)] = advice

    async def choose(
        players: list,
        *,
        bank: int,
        free_transfers: int,
        squad_notes: list,
        team_names: dict,
        fixtures_by_team: dict,
        settings: Settings,
        allow_llm: bool,
        client: object = None,
    ) -> TransferSuggestion:
        seen["choose"] += 1
        seen["allow"] = allow_llm
        seen["ft"] = free_transfers
        return TransferSuggestion(
            action="roll",
            free_transfers=free_transfers,
            moves=[],
            summary="Roll both free transfers. No move is a clear upgrade.",
            source="policy" if not allow_llm else "llm",
        )

    def cap(conn: object, limit: int) -> bool:
        seen["cap"] += 1
        return True

    monkeypatch.setattr(services, "load_merged_entry", load)
    monkeypatch.setattr(services, "snapshot_from_cache", lambda *args, **kwargs: _snapshot(squad))
    monkeypatch.setattr(services, "current_season_id", lambda conn: "2026/27")
    monkeypatch.setattr(services, "_transfer_opts", lambda conn, snapshot, weights: [])
    monkeypatch.setattr(services.stats_repo, "next_gw_id", lambda conn, season_id: 12)
    monkeypatch.setattr(services, "_transfer_fixtures", lambda conn, season_id, next_gw: {})
    monkeypatch.setattr(services, "get_suggested_transfers", get)
    monkeypatch.setattr(services, "save_suggested_transfers", save)
    monkeypatch.setattr(services, "choose_transfers", choose)
    monkeypatch.setattr(services, "try_llm_cap", cap)
    return seen


def _settings(**overrides: object) -> Settings:
    values = {"llm_api_key": "test-key", "llm_model": "test/model", "llm_daily_call_cap": 200}
    values.update(overrides)
    return Settings(**values)


async def test_cached_transfer_plan_skips_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    squad = _squad()
    seen = _wire(monkeypatch, squad)
    conn = _Conn(weights={"form": 0.4})
    first = await services.build_suggested_transfers(conn, _settings(), "user-1")
    second = await services.build_suggested_transfers(conn, _settings(), "user-1")

    assert first["action"] == "roll"
    assert second == first
    assert seen["choose"] == 1
    assert seen["cap"] == 1
    assert seen["ft"] == 2
    assert conn.commits == 2


async def test_weight_change_asks_again(monkeypatch: pytest.MonkeyPatch) -> None:
    squad = _squad()
    seen = _wire(monkeypatch, squad)
    conn = _Conn(weights={"form": 0.2})
    await services.build_suggested_transfers(conn, _settings(), "user-1")
    conn.weights = {"form": 0.9}
    await services.build_suggested_transfers(conn, _settings(), "user-1")
    assert seen["choose"] == 2


async def test_missing_model_does_not_spend_the_daily_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    squad = _squad()
    seen = _wire(monkeypatch, squad)
    conn = _Conn(weights={"form": 1})
    result = await services.build_suggested_transfers(conn, _settings(llm_api_key="", llm_model=""), "user-1")
    assert seen["cap"] == 0
    assert seen["allow"] is False
    assert result["source"] == "policy"
    assert result["incomings"] == []


def test_transfer_hash_uses_the_saved_weights() -> None:
    squad = _squad()
    weights = {"form": 0.4}
    digest = transfer_cache_hash(
        [player["element"] for player in squad],
        weights,
        2,
        15,
        {str(player["element"]): 50 for player in squad},
    )
    assert digest != transfer_cache_hash(
        [player["element"] for player in squad],
        weights,
        1,
        15,
        {str(player["element"]): 50 for player in squad},
    )


def test_suggested_transfers_round_trip_uses_the_full_key() -> None:
    advice = {"action": "roll", "moves": [], "summary": "Roll.", "source": "policy"}
    conn = _Conn(weights=None)
    conn.execute = lambda sql, params=None: _remember(conn, sql, params, {"advice": advice})  # type: ignore[method-assign]
    found = get_suggested_transfers(conn, "user-1", 42, 12, "abc")
    sql, params = conn.statements[0]
    assert "from suggested_transfers" in sql
    assert params == ["user-1", 42, 12, "abc"]
    assert found == advice

    save_suggested_transfers(conn, user_id="user-1", entry_id=42, gameweek=12, squad_hash="abc", advice=advice)
    insert, values = conn.statements[1]
    assert "insert into suggested_transfers" in insert
    assert "on conflict (user_id, entry_id, gameweek, squad_hash)" in insert
    assert values[:4] == ["user-1", 42, 12, "abc"]


def _remember(conn: _Conn, sql: str, params: list | None, row: dict) -> _Result:
    conn.statements.append((" ".join(sql.split()), list(params) if params is not None else None))
    return _Result(row)
