import pytest
from fastapi import HTTPException

from api.weights_query import parse_weights_query
from fplcore.models import ChipUsed, EntryHistoryRow
from fplcore.stats.insights import defensive_leaders, finishing_variance
from fplcore.stats.market import price_pressure
from fplcore.stats.report import (
    overperforming_players,
    performing_players,
    squad_score_for_xi,
    underperforming_players,
    xi_element_ids,
    xi_expected_points,
)
from fplcore.stats.season import captain_returns, season_rows, season_summary
from fplcore.stats.squad import template_threats


def _player(**overrides: object) -> dict:
    base = {
        "id": 1,
        "web_name": "Palmer",
        "team_short": "CHE",
        "position_id": 3,
        "now_cost": 100,
        "selected_by_percent": 10.0,
        "transfers_in_event": 0,
        "transfers_out_event": 0,
        "minutes": 540,
        "starts": 6,
        "goals_scored": 4,
        "assists": 2,
        "expected_goals": 5.0,
        "expected_assists": 1.5,
        "expected_goal_involvements": 6.5,
        "bonus": 8,
        "bps": 180,
        "form": 5.0,
        "recent_minutes": 540,
        "recent_points": 40,
        "recent_xgi": 4.0,
        "recent_dc": 60,
        "dc_hits": 4,
        "dc_starts": 6,
    }
    return {**base, **overrides}


def test_price_pressure_net_over_owners() -> None:
    players = [
        _player(id=1, web_name="In", selected_by_percent=10.0, transfers_in_event=200_000, transfers_out_event=0),
        _player(id=2, web_name="Out", selected_by_percent=10.0, transfers_in_event=0, transfers_out_event=200_000),
    ]
    result = price_pressure(players, total_managers=10_000_000, n=10)
    assert result["likely_to_rise"][0]["id"] == 1
    assert result["likely_to_rise"][0]["pressure"] == 0.2
    assert result["likely_to_fall"][0]["id"] == 2
    assert result["likely_to_fall"][0]["pressure"] == -0.2


def test_defensive_hit_rate() -> None:
    rows = [
        _player(id=10, web_name="A", position_id=2, recent_dc=40, dc_hits=3, dc_starts=5, recent_minutes=450),
        _player(id=11, web_name="B", position_id=3, recent_dc=80, dc_hits=1, dc_starts=5, recent_minutes=450),
    ]
    leaders = defensive_leaders(rows, min_minutes=180, n=10)
    assert leaders[0]["id"] == 10
    assert leaders[0]["hit_rate"] == 0.6
    assert leaders[0]["threshold"] == 10
    assert leaders[1]["threshold"] == 12


def test_finishing_variance_splits_over_and_under() -> None:
    players = [
        _player(id=1, web_name="Due", goals_scored=1, assists=0, expected_goal_involvements=5.0, expected_goals=4.0),
        _player(id=2, web_name="Hot", goals_scored=8, assists=4, expected_goal_involvements=5.0, expected_goals=4.0),
    ]
    result = finishing_variance(players, min_minutes=180, n=10)
    assert result["underperformers"][0]["id"] == 1
    assert result["underperformers"][0]["xgi_delta"] == 4.0
    assert result["overperformers"][0]["id"] == 2
    assert result["overperformers"][0]["xgi_delta"] == -7.0


def test_captain_returns_includes_triple_captain() -> None:
    history = [EntryHistoryRow(event=1, points=24)]
    picks = {
        1: {
            "picks": [{"element": 10, "is_captain": True, "multiplier": 3}],
            "active_chip": "3xc",
        }
    }
    points = {(10, 1): 8, (11, 1): 6}
    names = {10: "Haaland", 11: "Salah"}
    result = captain_returns(history, picks, points, names, {1: 11})
    assert result["rows"][0]["points"] == 24
    assert result["rows"][0]["multiplier"] == 3
    assert result["rows"][0]["crowd_points"] == 12
    assert result["total"] == 24
    assert result["crowd_total"] == 12


def test_season_summary_best_worst_and_bench() -> None:
    history = [
        EntryHistoryRow(event=1, points=40, total_points=40, points_on_bench=4, event_transfers_cost=0, percentile_rank=40),
        EntryHistoryRow(event=2, points=80, total_points=120, points_on_bench=8, event_transfers_cost=4, percentile_rank=18),
    ]
    gameweeks = {
        1: {"average_entry_score": 50, "highest_score": 100},
        2: {"average_entry_score": 55, "highest_score": 120},
    }
    rows = season_rows(history, gameweeks, [ChipUsed(name="bboost", event=2)])
    summary = season_summary(rows)
    assert summary["best_gw"] == {"event": 2, "points": 80}
    assert summary["worst_gw"] == {"event": 1, "points": 40}
    assert summary["gws_above_average"] == 1
    assert summary["bench_points_total"] == 12
    assert summary["hit_cost_total"] == 4
    assert summary["latest_percentile"] == 18
    assert summary["total_points"] == 120
    assert rows[1]["chip"] == "bboost"
    assert rows[0]["delta_vs_avg"] == -10


def test_template_threats_skips_owned_and_ranks_by_ownership_times_proj() -> None:
    ranked = [
        _player(id=1, web_name="Salah", selected_by_percent=50, proj=20),
        _player(id=2, web_name="Haaland", selected_by_percent=80, proj=18),
        _player(id=3, web_name="Punt", selected_by_percent=8, proj=22),
    ]
    threats = template_threats(ranked, squad_ids={1}, min_ownership=20.0, n=10)
    assert [t["id"] for t in threats] == [2]
    assert threats[0]["threat"] == 1440.0


def test_xi_element_ids_takes_starting_eleven() -> None:
    squad = [{"element": i, "squad_position": i} for i in range(1, 16)]
    assert xi_element_ids(squad) == list(range(1, 12))


def _spread_field() -> list[float]:
    return [1.0, 2.0, 3.0, 4.0]


def test_squad_score_counts_the_captain_twice() -> None:
    field = _spread_field()
    # Eleven 2.5s is 27.5, plus the captain again is 30.
    # Forgetting the captain would land on 2.5 rather than 3.4.
    assert squad_score_for_xi([2.5] * 11, field) == 3.4


def test_squad_score_premium_xi_is_ten_and_ordinary_xi_is_zero() -> None:
    field = _spread_field()
    # 98th percentile of 1..4 is 3.94. Twelve of those (XI + captain) is the top of the scale.
    assert squad_score_for_xi([3.94] * 11, field) == 10.0
    assert squad_score_for_xi([10.0] * 11, field) == 10.0
    # 25th percentile is 1.75, so an XI below that scores 0.
    assert squad_score_for_xi([1.0] * 11, field) == 0.0


def test_squad_score_ignores_players_without_a_fixture() -> None:
    assert squad_score_for_xi([2.5] * 11, [0.0, 0.0, 1.0, 2.0, 3.0, 4.0]) == 3.4


def test_squad_score_flat_field_is_five() -> None:
    assert squad_score_for_xi([3.0] * 11, [3.0, 3.0, 3.0]) == 5.0
    assert squad_score_for_xi([], []) == 0.0


def test_squad_score_short_xi_pads_with_zeros() -> None:
    assert squad_score_for_xi([4.0], _spread_field()) == 0.0


def test_squad_score_ignores_players_past_the_xi() -> None:
    assert squad_score_for_xi([2.5] * 11 + [100.0], _spread_field()) == 3.4


def test_xi_expected_points_sums_projections() -> None:
    rows = {
        1: {
            "web_name": "Salah",
            "form_score": 1,
            "fixture_score": 1,
            "home_score": 1,
            "xgi_score": 1,
            "value_score": 1,
            "minutes_score": 1,
            "minutes": 900,
            "trend_score": 0,
            "fixture_count": 1,
            "status": "a",
            "chance_of_playing_next_round": 100,
        }
    }
    result = xi_expected_points([1, 2], rows)
    assert result["players"][0]["id"] == 1
    assert result["players"][0]["proj"] > 0
    assert result["players"][-1]["id"] == 2
    assert result["players"][-1]["proj"] == 0.0
    assert result["total"] == result["players"][0]["proj"]


def test_performing_and_underperforming_stay_inside_squad() -> None:
    recent = [
        _player(id=1, web_name="Hot", recent_points=50, recent_minutes=540),
        _player(id=2, web_name="Out", recent_points=80, recent_minutes=540),
    ]
    players = [
        _player(id=1, web_name="Due", goals_scored=1, assists=0, expected_goal_involvements=5.0),
        _player(id=3, web_name="Hot", goals_scored=8, assists=2, expected_goal_involvements=1.0),
        _player(id=4, web_name="Level", goals_scored=3, assists=0, expected_goal_involvements=3.2),
        _player(id=9, web_name="Other", goals_scored=0, assists=0, expected_goal_involvements=9.0),
        _player(id=10, web_name="Outside", goals_scored=12, assists=4, expected_goal_involvements=0.5),
    ]
    performing = performing_players(recent, {1})
    under = underperforming_players(players, {1, 3, 4})
    over = overperforming_players(players, {1, 3, 4})
    assert [p["id"] for p in performing] == [1]
    assert [p["id"] for p in under] == [1]
    assert [p["id"] for p in over] == [3]


def test_parse_weights_query_none() -> None:
    assert parse_weights_query(None) is None


def test_parse_weights_query_valid() -> None:
    assert parse_weights_query('{"form": 0.4, "xgi": 0.6}') == {"form": 0.4, "xgi": 0.6}


def test_parse_weights_query_rejects_invalid_json() -> None:
    with pytest.raises(HTTPException) as err:
        parse_weights_query("{")
    assert err.value.status_code == 422


def test_parse_weights_query_rejects_non_object() -> None:
    with pytest.raises(HTTPException) as err:
        parse_weights_query("[1, 2]")
    assert err.value.status_code == 422


def test_parse_weights_query_rejects_unknown_key() -> None:
    with pytest.raises(HTTPException) as err:
        parse_weights_query('{"luck": 1}')
    assert err.value.status_code == 422


def test_parse_weights_query_rejects_negative() -> None:
    with pytest.raises(HTTPException) as err:
        parse_weights_query('{"form": -0.1}')
    assert err.value.status_code == 422


def test_parse_weights_query_rejects_non_number() -> None:
    with pytest.raises(HTTPException) as err:
        parse_weights_query('{"form": "high"}')
    assert err.value.status_code == 422
