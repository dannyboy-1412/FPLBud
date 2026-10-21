from pathlib import Path

from fplcore.models import BootstrapStatic, Element, Event

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_element_casts_string_numerics() -> None:
    el = Element.model_validate(
        {
            "id": 1,
            "code": 10,
            "web_name": "Palmer",
            "team": 6,
            "element_type": 3,
            "status": "a",
            "now_cost": 106,
            "cost_change_start": 6,
            "cost_change_event": 0,
            "selected_by_percent": "42.1",
            "transfers_in_event": 1,
            "transfers_out_event": 0,
            "form": "6.5",
            "points_per_game": "5.2",
            "total_points": 40,
            "minutes": 540,
            "starts": 6,
            "expected_goals": "1.80",
            "expected_assists": "0.90",
            "expected_goal_involvements": "2.70",
            "expected_goals_conceded": "3.10",
            "can_transact": True,
        }
    )
    assert el.form == 6.5
    assert el.expected_goals == 1.8
    assert el.selected_by_percent == 42.1


def test_bootstrap_sample_exposes_stats_fields() -> None:
    path = SAMPLES / "bootstrap-static.json"
    if not path.exists():
        return
    data = BootstrapStatic.model_validate_json(path.read_text(encoding="utf-8"))
    el = data.elements[0]
    assert el.transfers_in >= 0
    assert el.transfers_out >= 0
    assert el.event_points >= 0
    assert el.goals_scored >= 0
    assert el.bonus >= 0
    assert el.penalties_order is None or el.penalties_order >= 1
    finished = [event for event in data.events if event.finished]
    assert finished
    last = finished[-1]
    assert last.most_captained is not None
    assert last.highest_score is not None
    Event.model_validate(last.model_dump())
    assert data.total_players > 0
