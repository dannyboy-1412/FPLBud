from fplcore.team_import import snapshot_from_row


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
