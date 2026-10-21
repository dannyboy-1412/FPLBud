from datetime import UTC, datetime

from api.services import with_pitch_details
from fplcore.models import ChipUsed, EntryHistoryRow
from fplcore.team_import import derive_free_transfers, estimate_selling_price


def test_free_transfers_sample_entry_gw7() -> None:
    history = [
        EntryHistoryRow(event=1, event_transfers=0, event_transfers_cost=0),
        EntryHistoryRow(event=2, event_transfers=1, event_transfers_cost=0),
        EntryHistoryRow(event=3, event_transfers=1, event_transfers_cost=0),
        EntryHistoryRow(event=4, event_transfers=1, event_transfers_cost=0),
        EntryHistoryRow(event=5, event_transfers=1, event_transfers_cost=0),
        EntryHistoryRow(event=6, event_transfers=2, event_transfers_cost=4),
    ]
    ft = derive_free_transfers(history, [], next_event=7)
    assert ft == 1


def test_wildcard_does_not_consume_ft() -> None:
    history = [
        EntryHistoryRow(event=1, event_transfers=0, event_transfers_cost=0),
        EntryHistoryRow(event=2, event_transfers=8, event_transfers_cost=0),
    ]
    chips = [ChipUsed(name="wildcard", event=2, time=datetime.now(UTC))]
    ft = derive_free_transfers(history, chips, next_event=3)
    assert ft == 1


def test_selling_price_half_of_rise() -> None:
    assert estimate_selling_price(player_id=1, now_cost=110, cost_change_start=10, transfers=[]) == 105
    assert estimate_selling_price(player_id=1, now_cost=90, cost_change_start=-10, transfers=[]) == 90


def test_pitch_details_attach_club_and_opponent() -> None:
    players = [{"element": 1, "team_id": 14, "web_name": "Salah"}]
    detailed = with_pitch_details(
        players,
        {14: "LIV"},
        {14: [{"opponent": "ARS", "fdr": 4, "is_home": True}]},
    )
    assert detailed[0]["team_short"] == "LIV"
    assert detailed[0]["fixtures"] == [{"opponent": "ARS", "fdr": 4, "is_home": True}]
    assert detailed[0]["web_name"] == "Salah"
    assert players[0] == {"element": 1, "team_id": 14, "web_name": "Salah"}
