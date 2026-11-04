from api.chat.context import fingerprint
from api.chat.history import prompt_messages
from fplcore.chat.prompt import ContextView, SquadRow, render_context, render_context_update
from fplcore.team_import import snapshot_from_row, snapshot_lags_published


def test_snapshot_from_row_reads_stored_tenths() -> None:
    snapshot = snapshot_from_row(
        {
            "entry_id": 7,
            "event": 5,
            "season_id": "2026/27",
            "picks": [{"element": 10, "position": 1, "is_captain": True}],
            "bank": 15,
            "team_value": 1000,
            "free_transfers": 2,
            "selling_prices": '{"10": 55}',
            "chips_available": [{"name": "wildcard"}],
            "chips_used": [],
            "active_chip": None,
            "flags": [],
            "overrides": None,
            "content_hash": "abc",
        },
        name="Town",
        manager="Alex",
    )
    assert snapshot.entry_id == 7
    assert snapshot.name == "Town"
    assert snapshot.bank == 15
    assert snapshot.selling_prices == {"10": 55}
    assert snapshot.squad_players == []


def test_snapshot_lags_only_when_a_later_gameweek_is_published() -> None:
    assert snapshot_lags_published(6, 9)
    assert snapshot_lags_published(None, 9)
    assert not snapshot_lags_published(9, 9)
    assert not snapshot_lags_published(10, 9)
    assert not snapshot_lags_published(6, None)


def test_context_update_names_the_published_squad() -> None:
    previous = ContextView(
        snapshot_id=2,
        snapshot_gw=6,
        starters=[SquadRow(368, "Szoboszlai", "LIV", "MID", 6.7, 0.8, "a")],
    )
    current = ContextView(
        snapshot_id=9,
        snapshot_gw=9,
        has_team=True,
        starters=[SquadRow(411, "Haaland", "MCI", "FWD", 15.8, 5.5, "a")],
        bench=[SquadRow(259, "Diop", "IPS", "DEF", 3.9, 3.4, "a")],
        captain_id=411,
        captain_name="Haaland",
    )
    update = render_context_update(previous, current)
    assert update is not None
    assert "out of date" in update
    assert "411 Haaland" in update
    assert "259 Diop" in update
    assert "Szoboszlai" not in update


def test_prompt_repins_the_squad_when_the_snapshot_changes() -> None:
    previous = ContextView(
        snapshot_id=2,
        snapshot_gw=6,
        has_team=True,
        season_id="2026/27",
        starters=[SquadRow(368, "Szoboszlai", "LIV", "MID", 6.7, 0.8, "a")],
    )
    current = ContextView(
        snapshot_id=9,
        snapshot_gw=9,
        has_team=True,
        season_id="2026/27",
        starters=[SquadRow(411, "Haaland", "MCI", "FWD", 15.8, 5.5, "a")],
    )
    _messages, pinned, to_pin, update = prompt_messages(
        canary="canary",
        view=current,
        stored_context={"text": render_context(previous), "fingerprint": fingerprint(previous)},
        history_rows=[],
        history_budget=2000,
    )
    assert "411 Haaland" in pinned
    assert "Szoboszlai" not in pinned
    assert to_pin is not None
    assert to_pin["fingerprint"]["snapshot_id"] == 9
    assert update is not None
    assert "411 Haaland" in update
