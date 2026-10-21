import pandas as pd

from fplcore.metrics.combine import (
    availability,
    combined_score,
    projected_points,
    renormalise_weights,
)
from fplcore.metrics.compute import compute_player_metrics


def test_renormalise_and_availability() -> None:
    w = renormalise_weights({"form": 0.3, "fixture": 0.3, "home": 0.1, "xgi": 0.3})
    assert abs(sum(w.values()) - 1) < 1e-9
    assert availability(chance_of_playing_next_round=50, status="d", k=1) == 0.5
    assert availability(chance_of_playing_next_round=None, status="a", k=1) == 1.0
    assert availability(chance_of_playing_next_round=None, status="u", k=1) == 0.0
    assert projected_points(score=1.0, fixture_count=0, avail=1) == 0
    assert projected_points(score=1.0, fixture_count=1, avail=1) == 7.0


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
    assert len(gw7) == 2
    haaland = next(r for r in gw7 if r.player_id == 1)
    assert haaland.fixture_count == 1
    assert haaland.fixture_score == 0.75
    assert haaland.home_score == 1.0
    assert haaland.form_score >= 0.5


def test_combined_score_uses_weights() -> None:
    score = combined_score(
        {"form": 1, "fixture": 0, "home": 0, "xgi": 0, "value": 0, "minutes": 0, "trend": 0},
        {"form": 1, "fixture": 0, "home": 0, "xgi": 0},
    )
    assert abs(score - 1) < 1e-9
