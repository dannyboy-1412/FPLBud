from decimal import Decimal

import pandas as pd

from fplcore.metrics.combine import (
    availability,
    combined_score,
    playing_share,
    projected_points,
    renormalise_weights,
)
from fplcore.metrics.compute import (
    compute_minutes_raw,
    compute_player_metrics,
    fixture_features_for_gw,
    team_form_ratings,
)


def test_renormalise_and_availability() -> None:
    w = renormalise_weights({"form": 0.3, "fixture": 0.3, "home": 0.1, "xgi": 0.3})
    assert abs(sum(w.values()) - 1) < 1e-9
    assert availability(chance_of_playing_next_round=50, status="d", k=1) == 0.5
    assert availability(chance_of_playing_next_round=None, status="a", k=1) == 1.0
    assert availability(chance_of_playing_next_round=None, status="u", k=1) == 0.0
    assert projected_points(score=1.0, fixture_count=0, avail=1) == 0
    assert projected_points(score=1.0, fixture_count=1, avail=1) == 7.0
    assert playing_share(0.9, 0) == 0.0
    assert projected_points(score=1.0, fixture_count=1, avail=1, minutes=0) == 0
    full = projected_points(score=0.5, fixture_count=1, avail=1, minutes=1)
    assert projected_points(score=0.5, fixture_count=1, avail=1, minutes=0.5) == full * 0.5


def test_compute_metrics_smoke() -> None:
    players = pd.DataFrame(
        [
            {
                "id": 1,
                "team_id": 1,
                "position_id": 4,
                "form": 8.0,
                "points_per_game": 8.0,
                "now_cost": 140,
                "minutes": 540,
                "starts": 6,
                "status": "a",
                "chance_of_playing_next_round": 100,
                "transfers_in_event": 1000,
                "transfers_out_event": 100,
                "expected_goals_per_90": 0.6,
                "expected_assists_per_90": 0.2,
                "expected_goals_conceded_per_90": 1.0,
            },
            {
                "id": 2,
                "team_id": 2,
                "position_id": 4,
                "form": 2.0,
                "points_per_game": 2.0,
                "now_cost": 55,
                "minutes": 90,
                "starts": 1,
                "status": "a",
                "chance_of_playing_next_round": None,
                "transfers_in_event": 10,
                "transfers_out_event": 200,
                "expected_goals_per_90": 0.1,
                "expected_assists_per_90": 0.05,
                "expected_goals_conceded_per_90": 1.4,
            },
            {
                "id": 3,
                "team_id": 1,
                "position_id": 1,
                "form": 0.0,
                "points_per_game": 0.0,
                "now_cost": 45,
                "minutes": 0,
                "starts": 0,
                "status": "a",
                "chance_of_playing_next_round": None,
                "transfers_in_event": 0,
                "transfers_out_event": 0,
                "expected_goals_per_90": 0.0,
                "expected_assists_per_90": 0.0,
                "expected_goals_conceded_per_90": 1.2,
            },
        ]
    )
    history = pd.DataFrame(
        [
            {
                "player_id": 1,
                "round": r,
                "minutes": 90,
                "starts": 1,
                "total_points": 8,
                "expected_goals": 0.5,
                "expected_assists": 0.2,
                "expected_goals_conceded": 1.0,
            }
            for r in range(1, 6)
        ]
        + [
            {
                "player_id": 2,
                "round": r,
                "minutes": 20,
                "starts": 0,
                "total_points": 1,
                "expected_goals": 0.0,
                "expected_assists": 0.0,
                "expected_goals_conceded": 1.0,
            }
            for r in range(1, 6)
        ]
    )
    for column in ("expected_goals", "expected_assists", "expected_goals_conceded"):
        history[column] = history[column].map(Decimal)
    fixtures = pd.DataFrame(
        [
            {
                "id": 1,
                "event": 7,
                "team_h": 1,
                "team_a": 2,
                "team_h_difficulty": 2,
                "team_a_difficulty": 4,
            }
        ]
    )
    rows = compute_player_metrics(
        players=players,
        history=history,
        fixtures=fixtures,
        snapshots=pd.DataFrame(),
        next_gw=7,
        last_rounds=[2, 3, 4, 5, 6],
        total_players=10_000_000,
        hours_since_deadline=24,
    )
    gw7 = [r for r in rows if r.computed_for_gw == 7]
    assert len(gw7) == 3
    haaland = next(r for r in gw7 if r.player_id == 1)
    assert haaland.fixture_count == 1
    assert haaland.fixture_score == 0.75
    assert haaland.home_score == 1.0
    assert haaland.form_score >= 0.5
    keeper = next(r for r in gw7 if r.player_id == 3)
    assert keeper.xgi_raw > 0


def _player(player_id: int, team_id: int, position_id: int) -> dict:
    return {
        "id": player_id,
        "team_id": team_id,
        "position_id": position_id,
        "form": 1.0,
        "points_per_game": 2.0,
        "now_cost": 50,
        "minutes": 400,
        "starts": 4,
        "status": "a",
        "chance_of_playing_next_round": 100,
        "transfers_in_event": 0,
        "transfers_out_event": 0,
        "expected_goals_per_90": 0.1,
        "expected_assists_per_90": 0.05,
        "expected_goals_conceded_per_90": 1.0,
    }


def _appearances(player_id: int, starts: list[int], minutes: list[int]) -> list[dict]:
    rows = []
    for rnd, started, played in zip(range(1, len(starts) + 1), starts, minutes, strict=True):
        rows.append(
            {
                "player_id": player_id,
                "round": rnd,
                "minutes": played,
                "starts": started,
                "total_points": 2,
                "expected_goals": 0.1,
                "expected_assists": 0.0,
                "expected_goals_conceded": 0.5,
            }
        )
    return rows


def test_recent_starts_count_more_than_a_flat_average() -> None:
    players = pd.DataFrame([_player(1, 1, 3)])
    history = pd.DataFrame(_appearances(1, [0, 0, 1, 1, 1, 1], [0, 0, 90, 90, 90, 90]))
    score = float(compute_minutes_raw(players, history).iloc[0])
    assert score >= 0.85
    assert score > 4 / 6


def test_a_seventy_minute_starter_keeps_most_of_his_projection() -> None:
    players = pd.DataFrame([_player(1, 1, 3)])
    history = pd.DataFrame(_appearances(1, [1, 1, 1, 1, 1, 1], [70, 70, 70, 70, 70, 70]))
    score = float(compute_minutes_raw(players, history).iloc[0])
    assert 0.84 <= score <= 0.87


def test_a_new_run_of_starts_beats_the_flat_minutes_average() -> None:
    players = pd.DataFrame([_player(1, 1, 3)])
    minutes = [0, 0, 71, 85, 71, 65]
    history = pd.DataFrame(_appearances(1, [0, 0, 1, 1, 1, 1], minutes))
    score = float(compute_minutes_raw(players, history).iloc[0])
    started = [played / 90 for played in minutes if played]
    flat = (4 / 6) * (sum(started) / len(started))
    assert score > flat


def test_fixture_ease_stays_on_fdr_without_finished_matches() -> None:
    players = pd.DataFrame([_player(1, 1, 3)])
    fixtures = pd.DataFrame(
        [{"id": 1, "event": 10, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4}]
    )
    ease, home, counts = fixture_features_for_gw(players, fixtures, 10)
    assert float(ease.iloc[0]) == 0.75
    assert float(home.iloc[0]) == 1.0
    assert int(counts.iloc[0]) == 1


def test_a_leaky_opponent_raises_attacker_ease_above_the_fdr() -> None:
    players = pd.DataFrame([_player(1, 1, 3), _player(2, 2, 2)])
    upcoming = pd.DataFrame(
        [{"id": 9, "event": 10, "team_h": 2, "team_a": 1, "team_h_difficulty": 2, "team_a_difficulty": 4}]
    )
    history_rows = []
    for rnd in range(1, 7):
        history_rows.append(
            {
                "player_id": 11,
                "round": rnd,
                "opponent_team": 2,
                "expected_goals": 2.0,
                "team_id": 1,
            }
        )
        history_rows.append(
            {
                "player_id": 22,
                "round": rnd,
                "opponent_team": 1,
                "expected_goals": 0.2,
                "team_id": 2,
            }
        )
    ratings = team_form_ratings(pd.DataFrame(history_rows), pd.DataFrame(), players)
    ease, _, _ = fixture_features_for_gw(players, upcoming, 10, ratings)
    attacker = float(ease.iloc[0])
    assert attacker > 0.25

    defender_ease, _, _ = fixture_features_for_gw(players, upcoming, 10, ratings)
    assert float(defender_ease.iloc[1]) < 0.75


def test_combined_score_uses_weights() -> None:
    score = combined_score(
        {"form": 1, "fixture": 0, "home": 0, "xgi": 0, "value": 0, "minutes": 0, "trend": 0},
        {"form": 1, "fixture": 0, "home": 0, "xgi": 0, "value": 0, "minutes": 0},
    )
    assert abs(score - 1) < 1e-9
