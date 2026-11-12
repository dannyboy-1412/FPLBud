from fplcore.stats.attention import apply_live_flags, fixture_runs, squad_attention

WEEKS = [10, 11, 12]


def _fix(opponent: str, fdr: int, *, home: bool = True) -> dict:
    return {"opponent": opponent, "fdr": fdr, "is_home": home}


def _fixtures(*ratings: int, blanks: set[int] | None = None) -> dict[int, list[dict]]:
    skipped = blanks or set()
    return {gw: [] if gw in skipped else [_fix("WOL" if i == 0 else "BUR" if i == 1 else "EVE", fdr)] for i, (gw, fdr) in enumerate(zip(WEEKS, ratings, strict=True))}


def _player(player_id: int, name: str, **overrides: object) -> dict:
    base = {
        "id": player_id,
        "web_name": name,
        "team_short": "ARS",
        "team_id": 1,
        "position_id": 3,
        "now_cost": 60,
        "selected_by_percent": 12.0,
        "status": "a",
        "chance_of_playing_next_round": None,
        "news": "",
        "minutes": 540,
        "recent_minutes": 450,
        "recent_starts": 5,
        "recent_matches": 6,
    }
    return {**base, **overrides}


def _runs(players: list[dict], by_team: dict[int, dict[int, list[dict]]]) -> dict:
    return fixture_runs(players, gameweeks=WEEKS, fixtures_by_team=by_team, min_minutes=180, n=10)


def _squad(players: list[dict], squad: set[int], by_team: dict[int, dict[int, list[dict]]]) -> dict:
    return squad_attention(players, squad, gameweeks=WEEKS, fixtures_by_team=by_team)


def test_flagged_player_is_sorted_out_and_not_left_alone() -> None:
    players = [
        _player(1, "Gabriel", status="d", chance_of_playing_next_round=75, news=""),
        _player(2, "Rice"),
    ]
    by_team = {1: _fixtures(2, 2, 2)}
    result = _squad(players, {1, 2}, by_team)
    assert [row["id"] for row in result["sort_out"]] == [1]
    assert result["sort_out"][0]["detail"].startswith("Doubtful, 75%.")
    assert "Started 5 of the last 6." in result["sort_out"][0]["detail"]
    assert [row["id"] for row in result["leave_alone"]] == [2]
    assert result["leave_alone"][0]["run"] == "H WOL (2) · H BUR (2) · H EVE (2)"


def test_news_replaces_the_status_label() -> None:
    players = [_player(1, "Gabriel", status="i", news="Knee injury - expected back 20 Nov")]
    result = _squad(players, {1}, {1: _fixtures(2, 2, 2)})
    assert result["sort_out"][0]["detail"].startswith("Knee injury - expected back 20 Nov.")


def test_short_of_starts_is_sorted_out_even_with_an_easy_run() -> None:
    players = [_player(1, "Tonali", recent_starts=2, recent_matches=6)]
    result = _squad(players, {1}, {1: _fixtures(2, 2, 2)})
    assert result["sort_out"][0]["detail"] == "Started 2 of the last 6."
    assert result["leave_alone"] == []


def test_hard_run_is_sorted_out_without_a_minutes_complaint() -> None:
    players = [_player(1, "Isak", team_id=2, team_short="LIV")]
    result = _squad(players, {1}, {2: _fixtures(4, 5, 4, blanks=set())})
    assert [row["id"] for row in result["sort_out"]] == [1]
    assert result["sort_out"][0]["detail"] == "Started 5 of the last 6."
    assert result["sort_out"][0]["run"] == "H WOL (4) · H BUR (5) · H EVE (4)"
    assert result["leave_alone"] == []


def test_four_starts_from_six_counts_as_secure() -> None:
    players = [_player(1, "Rice", recent_starts=4, recent_matches=6)]
    result = _squad(players, {1}, {1: _fixtures(2, 2, 2)})
    assert [row["id"] for row in result["leave_alone"]] == [1]


def test_half_the_starts_is_still_a_problem() -> None:
    players = [_player(1, "Tonali", recent_starts=3, recent_matches=6)]
    result = _squad(players, {1}, {1: _fixtures(2, 2, 2)})
    assert result["sort_out"][0]["detail"] == "Started 3 of the last 6."
    assert result["leave_alone"] == []


def test_middle_run_is_on_neither_list() -> None:
    players = [_player(1, "Rice")]
    result = _squad(players, {1}, {1: _fixtures(3, 3, 3)})
    assert result["sort_out"] == []
    assert result["leave_alone"] == []


def test_too_few_matches_does_not_invent_a_minutes_problem() -> None:
    players = [_player(1, "New", recent_starts=1, recent_matches=2)]
    result = _squad(players, {1}, {1: _fixtures(2, 2, 2)})
    assert result["sort_out"] == []
    assert result["leave_alone"] == []


def test_players_outside_the_squad_are_ignored() -> None:
    players = [_player(1, "Mine", status="d", chance_of_playing_next_round=0), _player(9, "Other", status="u")]
    result = _squad(players, {1}, {1: _fixtures(2, 2, 2)})
    assert [row["id"] for row in result["sort_out"]] == [1]


def test_a_blank_is_called_out_on_its_own() -> None:
    players = [_player(1, "Saka")]
    result = _squad(players, {1}, {1: _fixtures(2, 2, 2, blanks={11})})
    assert result["sort_out"][0]["detail"] == "Started 5 of the last 6. No game in the next three."
    assert "Blank" in result["sort_out"][0]["run"]
    assert result["leave_alone"] == []


def test_the_bigger_doubt_is_listed_first() -> None:
    players = [
        _player(1, "Later", status="d", chance_of_playing_next_round=75),
        _player(2, "Out", status="i", chance_of_playing_next_round=0, news=""),
    ]
    result = _squad(players, {1, 2}, {1: _fixtures(2, 2, 2)})
    assert [row["id"] for row in result["sort_out"]] == [2, 1]


def test_missing_fixtures_do_not_invent_blanks() -> None:
    players = [
        _player(1, "Gabriel", status="d", chance_of_playing_next_round=50, news=""),
        _player(2, "Rice"),
    ]
    result = squad_attention(players, {1, 2}, gameweeks=WEEKS, fixtures_by_team={})
    assert [row["id"] for row in result["sort_out"]] == [1]
    assert result["sort_out"][0]["run"] == ""
    assert "No game" not in result["sort_out"][0]["detail"]
    assert result["leave_alone"] == []
    assert _runs(players, {}) == {"easy": [], "hard": []}


def test_fixture_runs_split_kind_and_nasty_and_skip_the_middle() -> None:
    players = [
        _player(1, "Easy", team_id=1, recent_minutes=400),
        _player(2, "Hard", team_id=2, recent_minutes=400),
        _player(3, "Mid", team_id=3, recent_minutes=400),
        _player(4, "Cold", team_id=1, recent_minutes=20, minutes=20),
        _player(5, "Hurt", team_id=4, status="i", news="", recent_minutes=400),
    ]
    by_team = {
        1: _fixtures(2, 2, 2),
        2: _fixtures(5, 4, 4),
        3: _fixtures(3, 3, 3),
        4: _fixtures(2, 2, 1),
    }
    result = _runs(players, by_team)
    assert [row["id"] for row in result["easy"]] == [1]
    assert [row["id"] for row in result["hard"]] == [2]
    assert "Started 5 of the last 6." in result["easy"][0]["detail"]


def test_easy_runs_skip_flags_and_rotation() -> None:
    players = [
        _player(1, "Nailed", team_id=1, recent_minutes=400),
        _player(2, "Rotated", team_id=1, recent_starts=2, recent_matches=6, recent_minutes=400),
        _player(3, "Doubt", team_id=1, status="d", chance_of_playing_next_round=75, news="", recent_minutes=400),
    ]
    result = _runs(players, {1: _fixtures(2, 2, 2)})
    assert [row["id"] for row in result["easy"]] == [1]


def test_a_single_blank_is_not_sold_as_an_easy_run() -> None:
    players = [_player(1, "Saka", recent_minutes=400)]
    result = _runs(players, {1: _fixtures(1, 1, 1, blanks={12})})
    assert result["easy"] == []
    assert result["hard"] == []


def test_live_flags_override_the_stored_row() -> None:
    stored = [_player(1, "Manzambi", status="a", chance_of_playing_next_round=None, news="")]
    live = apply_live_flags(
        stored,
        [{"element": 1, "status": "d", "chance_of_playing_next_round": 75, "news": "Calf injury - 75% chance of playing"}],
    )
    result = _squad(live, {1}, {1: _fixtures(2, 2, 2)})
    assert [row["id"] for row in result["sort_out"]] == [1]
    assert result["leave_alone"] == []
    assert result["sort_out"][0]["detail"].startswith("Calf injury - 75% chance of playing.")


def test_recent_rows_override_the_player_record() -> None:
    players = [_player(1, "Rice", recent_starts=6, recent_matches=6)]
    recent = {1: {"recent_starts": 1, "recent_matches": 6, "recent_minutes": 200}}
    result = squad_attention(
        players, {1}, recent=recent, gameweeks=WEEKS, fixtures_by_team={1: _fixtures(2, 2, 2)}
    )
    assert result["sort_out"][0]["detail"] == "Started 1 of the last 6."
