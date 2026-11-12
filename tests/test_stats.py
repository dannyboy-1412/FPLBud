import pytest
from fastapi import HTTPException

from api.services import public_team_view
from api.weights_query import parse_weights_query
from fplcore.models import ChipUsed, EntryHistoryRow
from fplcore.stats.insights import defensive_leaders
from fplcore.stats.market import price_pressure
from fplcore.stats.report import (
    StarterOutlook,
    explain_squad_score,
    performing_players,
    projection_for_row,
    score_starting_xi,
    squad_score_for_xi,
    xi_element_ids,
    xi_expected_points,
    xi_projections,
)
from fplcore.stats.season import captain_returns, season_rows, season_summary
from fplcore.stats.squad import template_threats
from fplcore.team_import import TeamSnapshot


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


def test_squad_score_averages_each_starter_once() -> None:
    field = _spread_field()
    # 2.5 sits between the 25th (1.75) and the 98th (3.94), so each starter is 3.4.
    assert squad_score_for_xi([2.5] * 11, field) == 3.4


def test_squad_score_premium_xi_is_ten_and_ordinary_xi_is_zero() -> None:
    field = _spread_field()
    # 98th percentile of 1..4 is 3.94. Every starter at that mark is a 10.
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
    # One premium starter is a 10, and the ten empty places are 0.
    assert squad_score_for_xi([4.0], _spread_field()) == 0.9


def test_squad_score_ignores_players_past_the_xi() -> None:
    assert squad_score_for_xi([2.5] * 11 + [100.0], _spread_field()) == 3.4


def _outlook(name: str, projection: float, **flags: bool) -> StarterOutlook:
    return StarterOutlook(name=name, projection=projection, **flags)


def test_squad_score_reason_for_a_premium_xi_says_all_eleven_are_strong() -> None:
    starters = [_outlook("Haaland", 3.94)] + [_outlook(f"P{i}", 3.94) for i in range(10)]
    scored = explain_squad_score(starters, _spread_field())
    assert scored.value == 10.0
    assert scored.notes.added == (
        "All 11 starters project 3.9 points, about 0.4 above the 3.5 points a strong pick needs.",
    )
    assert scored.notes.short_of_10 == ()
    assert scored.reason == scored.notes.added[0]


def test_squad_score_reason_for_an_ordinary_xi_names_who_keeps_it_off_10() -> None:
    scored = explain_squad_score([_outlook(f"P{i}", 2.5) for i in range(11)], _spread_field())
    assert scored.value == 3.4
    assert scored.notes.added == ()
    assert scored.notes.short_of_10 == (
        "All 11 starters project 2.5 points, about 1.0 short of the 3.5 points a strong pick needs. "
        "That is what keeps this off a 10.",
    )
    assert scored.reason == scored.notes.short_of_10[0]


def test_squad_score_reason_for_a_weak_xi_says_why_it_is_at_the_bottom() -> None:
    scored = explain_squad_score([_outlook(f"P{i}", 1.0) for i in range(11)], _spread_field())
    assert scored.value == 0.0
    assert scored.notes.added == ()
    assert scored.notes.short_of_10 == (
        "All 11 starters project 1.0 points, about 2.5 short of the 3.5 points a strong pick needs. "
        "That is what keeps this off a 10.",
    )
    assert scored.reason == scored.notes.short_of_10[0]


def test_squad_score_reason_names_blanks_holding_back_strong_picks() -> None:
    starters = [_outlook("Haaland", 3.94)] + [_outlook(f"P{i}", 3.94) for i in range(7)]
    starters += [_outlook(name, 0.0, blank=True) for name in ("Gordon", "Watkins", "Wood")]
    scored = explain_squad_score(starters, _spread_field())
    assert scored.value == 7.3
    assert scored.notes.added == (
        "Haaland, P0, P1, P2, P3, P4, P5 and P6 each project 3.9 points, "
        "about 0.4 above the 3.5 points a strong pick needs.",
    )
    assert scored.notes.short_of_10 == (
        "Gordon, Watkins and Wood have no game this week, so those places add nothing.",
    )
    assert scored.reason == f"{scored.notes.added[0]} {scored.notes.short_of_10[0]}"


def test_squad_score_reason_keeps_a_blank_when_the_rest_are_strong() -> None:
    starters = [_outlook("Haaland", 3.94)] + [_outlook(f"P{i}", 3.94) for i in range(9)]
    starters.append(_outlook("Gordon", 0.0, blank=True))
    scored = explain_squad_score(starters, _spread_field())
    assert scored.value == 9.1
    assert scored.notes.added == (
        "Haaland, P0, P1, P2, P3, P4, P5, P6, P7 and P8 each project 3.9 points, "
        "about 0.4 above the 3.5 points a strong pick needs.",
    )
    assert scored.notes.short_of_10 == ("Gordon has no game this week, so that place adds nothing.",)
    assert scored.reason == f"{scored.notes.added[0]} {scored.notes.short_of_10[0]}"


def test_squad_score_reason_names_every_blank() -> None:
    starters = [_outlook(f"P{i}", 3.94) for i in range(6)]
    starters += [
        _outlook(name, 0.0, blank=True) for name in ("Gordon", "Watkins", "Wood", "Isak", "Wissa")
    ]
    scored = explain_squad_score(starters, _spread_field())
    assert (
        "Gordon, Watkins, Wood, Isak and Wissa have no game this week, so those places add nothing."
        in scored.reason
    )
    assert "others" not in scored.reason


def test_squad_score_notes_list_each_reason_it_is_short_of_10() -> None:
    starters = [_outlook("Haaland", 3.94)] + [_outlook(f"P{i}", 3.2) for i in range(8)]
    starters += [_outlook("Gordon", 0.0, blank=True), _outlook("Saka", 1.0, unlikely=True)]
    scored = explain_squad_score(starters, _spread_field())
    assert scored.notes.added == (
        "Haaland projects 3.9 points, about 0.4 above the 3.5 points a strong pick needs.",
    )
    assert scored.notes.short_of_10 == (
        "Gordon has no game this week, so that place adds nothing.",
        "Saka might not play, which cuts the projected points.",
        "P0, P1, P2, P3, P4, P5, P6 and P7 each project 3.2 points, "
        "about 0.3 short of the 3.5 points a strong pick needs.",
    )


def test_squad_score_reason_names_a_player_who_is_unlikely_to_play() -> None:
    starters = [_outlook("Saka", 1.0, unlikely=True)] + [_outlook(f"P{i}", 2.5) for i in range(10)]
    scored = explain_squad_score(starters, _spread_field())
    assert "Saka might not play, which cuts the projected points." in scored.reason


def test_squad_score_reason_names_a_player_who_has_not_been_starting() -> None:
    starters = [_outlook("Wright", 0.0, not_starting=True)] + [_outlook(f"P{i}", 2.5) for i in range(10)]
    scored = explain_squad_score(starters, _spread_field())
    assert "Wright has not been starting, so minutes are not expected." in scored.reason


def test_squad_score_reason_for_starters_above_the_middle_of_the_field() -> None:
    scored = explain_squad_score([_outlook(f"P{i}", 3.2) for i in range(11)], _spread_field())
    assert scored.value == 6.6
    assert scored.notes.added == ()
    assert scored.notes.short_of_10 == (
        "All 11 starters project 3.2 points, about 0.3 short of the 3.5 points a strong pick needs. "
        "That is what keeps this off a 10.",
    )
    assert scored.reason == scored.notes.short_of_10[0]


def test_squad_score_reason_for_a_flat_field_and_for_no_field() -> None:
    flat = explain_squad_score([_outlook(f"P{i}", 3.0) for i in range(11)], [3.0, 3.0, 3.0])
    assert flat.value == 5.0
    assert flat.reason == "Players with a game all look the same this week, so this side sits in the middle."
    empty = explain_squad_score([], [])
    assert empty.value == 0.0
    assert empty.reason == "Not enough players have a game this week to score this side."


def test_squad_score_reason_explains_a_hard_fixture_and_names_the_strong_picks() -> None:
    strong = [_outlook(f"P{i}", 3.94) for i in range(10)]
    scored = explain_squad_score(strong + [_outlook("Pickford", 2.5, fixture=0.2)], _spread_field())
    assert "others" not in scored.reason
    assert scored.notes.short_of_10 == (
        "Pickford projects 2.5 points, with a hard fixture, about 1.0 short of the 3.5 points a strong pick needs. "
        "That is what keeps this off a 10.",
    )


def test_squad_score_reason_says_why_the_leading_picks_are_strong() -> None:
    starters = [
        _outlook("Tavernier", 3.94, fixture=0.85, xgi=0.9),
        _outlook("N.Jackson", 3.8, form=0.8),
        _outlook("Salah", 3.7),
        _outlook("Saka", 3.6),
    ]
    starters += [_outlook(f"P{i}", 2.0) for i in range(7)]
    scored = explain_squad_score(starters, _spread_field())
    assert scored.notes.added == (
        "4 starters are strong picks. Tavernier projects 3.9 points, "
        "with an easy fixture and strong underlying numbers, "
        "about 0.4 above the 3.5 points a strong pick needs.",
        "N.Jackson projects 3.8 points, with strong recent form, "
        "about 0.3 above the 3.5 points a strong pick needs.",
        "Salah and Saka are strong picks too, both on at least 3.6 points.",
    )
    assert "others" not in scored.reason
    assert scored.notes.short_of_10 == (
        "P0, P1, P2, P3, P4, P5 and P6 each project 2.0 points, "
        "about 1.5 short of the 3.5 points a strong pick needs. "
        "That is what keeps this off a 10.",
    )


def test_squad_score_reason_names_the_weakest_when_projections_differ() -> None:
    starters = [
        _outlook("Haaland", 3.94),
        _outlook("Saka", 3.2),
        _outlook("Gordon", 2.5),
        _outlook("Wood", 2.0),
    ]
    starters += [_outlook(f"P{i}", 3.94) for i in range(7)]
    scored = explain_squad_score(starters, _spread_field())
    assert scored.notes.short_of_10 == (
        "Wood (2.0) and Gordon (2.5) are the furthest below the 3.5 points a strong pick needs. "
        "Saka is short of it too. That is what keeps this off a 10.",
    )


def test_squad_score_reason_leads_with_the_higher_projection_when_marks_tie() -> None:
    starters = [_outlook("Tavernier", 3.94), _outlook("N.Jackson", 10.0)]
    starters += [_outlook(f"P{i}", 2.0) for i in range(9)]
    scored = explain_squad_score(starters, _spread_field())
    assert scored.notes.added[0].startswith("2 starters are strong picks. N.Jackson")
    assert scored.notes.added[1].startswith("Tavernier")


def test_squad_score_reason_for_a_short_xi() -> None:
    scored = explain_squad_score([_outlook("Haaland", 4.0)], _spread_field())
    assert scored.value == 0.9
    assert scored.notes.added == (
        "Haaland projects 4.0 points, about 0.5 above the 3.5 points a strong pick needs.",
    )
    assert scored.notes.short_of_10 == ("Only 1 of the 11 places is filled.",)
    assert scored.reason == f"{scored.notes.added[0]} {scored.notes.short_of_10[0]}"


def _score_row(name: str, **overrides: object) -> dict:
    row: dict[str, object] = {
        "web_name": name,
        "form_score": 0.5,
        "fixture_score": 0.5,
        "home_score": 0.5,
        "xgi_score": 0.5,
        "value_score": 0.5,
        "minutes_score": 1,
        "minutes": 900,
        "trend_score": 0,
        "fixture_count": 1,
        "status": "a",
        "chance_of_playing_next_round": 100,
    }
    row.update(overrides)
    return row


def test_score_starting_xi_names_the_blank_and_matches_the_number() -> None:
    rows = {i: _score_row(f"P{i}", xgi_score=(i % 10) / 10) for i in range(1, 40)}
    rows[1] = _score_row("Gordon", fixture_count=0)
    xi = list(range(1, 12))
    scored = score_starting_xi(xi, rows)
    field = [projection_for_row(row, None) for row in rows.values()]
    assert scored.value == squad_score_for_xi(xi_projections(xi, rows), field)
    assert "Gordon" in scored.reason
    assert "no game" in scored.reason


def test_score_starting_xi_names_an_injury_and_a_player_without_minutes() -> None:
    rows = {i: _score_row(f"P{i}", xgi_score=(i % 10) / 10) for i in range(1, 40)}
    rows[1] = _score_row("Saka", status="i", chance_of_playing_next_round=0)
    injured = score_starting_xi(list(range(1, 12)), rows)
    assert "Saka might not play, which cuts the projected points." in injured.reason

    rows[1] = _score_row("Wright", minutes=0)
    idle = score_starting_xi(list(range(1, 12)), rows)
    assert "Wright has not been starting, so minutes are not expected." in idle.reason


def test_public_team_view_includes_the_squad_score_reason() -> None:
    snapshot = TeamSnapshot(
        entry_id=1,
        event=1,
        season_id="2025/26",
        name="Team",
        manager="Manager",
        overall_rank=1,
        picks=[],
        bank=0,
        team_value=1000,
        free_transfers=1,
        selling_prices={},
        chips_available=[],
        chips_used=[],
        active_chip=None,
        flags=[],
    )
    view = public_team_view(
        snapshot,
        squad_score=6.2,
        squad_score_reason="Above the middle of the scale.",
    )
    assert view["squad_score"] == 6.2
    assert view["squad_score_reason"] == "Above the middle of the scale."
    assert view["squad_score_notes"] == {"added": [], "short_of_10": []}


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


def test_performing_players_stay_inside_squad() -> None:
    recent = [
        _player(id=1, web_name="Hot", recent_points=50, recent_minutes=540),
        _player(id=2, web_name="Out", recent_points=80, recent_minutes=540),
    ]
    performing = performing_players(recent, {1})
    assert [p["id"] for p in performing] == [1]


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
