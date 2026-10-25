from fplcore.db.repos import players_needing_history


def test_unsynced_players_with_minutes_are_fetched() -> None:
    current = {1: 900, 2: 0, 3: 45}
    assert players_needing_history(current, {}) == [1, 3]


def test_a_player_who_has_never_played_is_skipped() -> None:
    assert players_needing_history({1: 0, 2: 0}, {}) == []


def test_players_synced_at_the_current_minutes_are_skipped() -> None:
    current = {1: 900, 2: 45}
    assert players_needing_history(current, {1: 900, 2: 45}) == []


def test_a_minute_change_after_bootstrap_still_selects_the_player() -> None:
    current = {1: 990, 2: 45}
    synced = {1: 900, 2: 45}
    assert players_needing_history(current, synced) == [1]


def test_a_downward_minute_correction_is_refetched() -> None:
    assert players_needing_history({1: 80}, {1: 90}) == [1]
