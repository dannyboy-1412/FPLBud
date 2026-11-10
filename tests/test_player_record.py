from fplcore.stats.player_record import build_player_record, fdr_band


def _row(
    *,
    gw: int = 8,
    opp: str = "ARS",
    home: bool = True,
    fdr: int = 2,
    minutes: int = 90,
    points: int = 6,
    goals: int = 0,
    assists: int = 0,
    clean_sheets: int = 0,
    bonus: int = 0,
) -> dict:
    return {
        "round": gw,
        "opponent": opp,
        "was_home": home,
        "fdr": fdr,
        "minutes": minutes,
        "total_points": points,
        "goals_scored": goals,
        "assists": assists,
        "clean_sheets": clean_sheets,
        "bonus": bonus,
    }


def test_fdr_band_edges() -> None:
    assert fdr_band(1) == "easy"
    assert fdr_band(2) == "easy"
    assert fdr_band(3) == "medium"
    assert fdr_band(4) == "hard"
    assert fdr_band(5) == "hard"


def test_double_gameweek_counts_as_two_matches() -> None:
    record = build_player_record(
        [
            _row(gw=8, opp="CHE", home=True, fdr=2, points=6, goals=1),
            _row(gw=8, opp="ARS", home=False, fdr=4, points=2, bonus=1),
        ]
    )
    assert record["by_fdr"]["easy"]["matches"] == 1
    assert record["by_fdr"]["hard"]["matches"] == 1
    assert record["by_venue"]["home"]["points"] == 6
    assert record["by_venue"]["away"]["points"] == 2
    assert [match["gw"] for match in record["matches"]] == [8, 8]
    assert record["by_fdr"]["easy"]["goals"] == 1
    assert record["by_fdr"]["hard"]["bonus"] == 1


def test_unused_sub_is_excluded_from_the_average() -> None:
    record = build_player_record(
        [
            _row(minutes=0, points=0, fdr=2),
            _row(minutes=90, points=7, fdr=2),
        ]
    )
    easy = record["by_fdr"]["easy"]
    assert easy["matches"] == 2
    assert easy["appearances"] == 1
    assert easy["points"] == 7
    assert easy["points_per_appearance"] == 7.0
    assert easy["minutes"] == 90


def test_two_appearances_average_to_one_decimal() -> None:
    record = build_player_record(
        [
            _row(gw=8, points=4, fdr=3),
            _row(gw=7, points=3, fdr=3),
        ]
    )
    assert record["by_fdr"]["medium"]["points_per_appearance"] == 3.5


def test_empty_history() -> None:
    record = build_player_record([])
    assert record["matches"] == []
    assert record["by_fdr"]["easy"]["matches"] == 0
    assert record["by_fdr"]["easy"]["points_per_appearance"] is None
    assert record["by_venue"]["away"]["appearances"] == 0
