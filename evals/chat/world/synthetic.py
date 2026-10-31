"""Small public FPL world. No user rows. Frozen at a pre-deadline moment."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

SEASON = "2026/27"
FROZEN_NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
NEXT_GW = 9
USER_ID = "00000000-0000-4000-8000-000000000001"
ENTRY_ID = 1001
CAPTAIN_ID = 13

CLUBS = [
    (1, "Arsenal", "ARS"),
    (2, "Aston Villa", "AVL"),
    (3, "Bournemouth", "BOU"),
    (4, "Brentford", "BRE"),
    (5, "Brighton", "BHA"),
    (6, "Burnley", "BUR"),
    (7, "Chelsea", "CHE"),
    (8, "Crystal Palace", "CRY"),
    (9, "Everton", "EVE"),
    (10, "Fulham", "FUL"),
    (11, "Leeds", "LEE"),
    (12, "Liverpool", "LIV"),
    (13, "Man City", "MCI"),
    (14, "Man Utd", "MUN"),
    (15, "Newcastle", "NEW"),
    (16, "Nott'm Forest", "NFO"),
    (17, "Sunderland", "SUN"),
    (18, "Spurs", "TOT"),
    (19, "West Ham", "WHU"),
    (20, "Wolves", "WOL"),
]

# id, team, position, name, price in tenths, ownership
SQUAD = [
    (1, 1, 1, "Raya", 55, 18.0),
    (2, 2, 1, "Martinez", 50, 8.0),
    (3, 3, 2, "Senesi", 45, 6.0),
    (4, 4, 2, "Collins", 45, 4.0),
    (5, 5, 2, "Dunk", 45, 12.0),
    (6, 6, 2, "Esteve", 40, 2.0),
    (7, 7, 2, "Cucurella", 50, 22.0),
    (8, 8, 3, "Eze", 70, 15.0),
    (9, 9, 3, "Ndiaye", 65, 9.0),
    (10, 10, 3, "Iwobi", 60, 7.0),
    (11, 11, 3, "Aaronson", 55, 3.0),
    (12, 12, 3, "Salah", 140, 45.0),
    (13, 13, 4, "Haaland", 150, 55.0),
    (14, 14, 4, "Cunha", 75, 11.0),
    (15, 15, 4, "Isak", 105, 28.0),
]


def manifest() -> dict[str, Any]:
    return {
        "season": SEASON,
        "next_gw": NEXT_GW,
        "data_version": 1,
        "now": FROZEN_NOW.isoformat(),
        "user_id": USER_ID,
        "entry_id": ENTRY_ID,
        "captain_id": CAPTAIN_ID,
    }


def public_rows() -> dict[str, list[dict[str, Any]]]:
    deadline = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)
    players = [_player(*row) for row in SQUAD]
    players.extend(_rest(start=16))
    return {
        "seasons": [{"id": SEASON, "is_current": True, "total_players": len(players)}],
        "positions": [
            {"id": 1, "short_name": "GKP", "squad_select": 2, "squad_min_play": 1, "squad_max_play": 1},
            {"id": 2, "short_name": "DEF", "squad_select": 5, "squad_min_play": 3, "squad_max_play": 5},
            {"id": 3, "short_name": "MID", "squad_select": 5, "squad_min_play": 2, "squad_max_play": 5},
            {"id": 4, "short_name": "FWD", "squad_select": 3, "squad_min_play": 1, "squad_max_play": 3},
        ],
        "teams": [_team(*club) for club in CLUBS],
        "gameweeks": [
            _gw(8, "Gameweek 8", deadline - timedelta(days=7), finished=True, previous=True),
            _gw(9, "Gameweek 9", deadline, nxt=True),
            _gw(10, "Gameweek 10", deadline + timedelta(days=7)),
        ],
        "fixtures": _fixtures(deadline),
        "players": players,
        "player_metrics": [_metric(int(row["id"])) for row in players],
        "player_gameweek_stats": [_match(int(row["id"]), int(row["team_id"])) for row in players[:15]],
        "player_gw_points": [
            {"season_id": SEASON, "player_id": int(row["id"]), "round": 8, "total_points": 6}
            for row in players[:15]
        ],
        "player_daily_snapshots": [
            {
                "season_id": SEASON,
                "player_id": int(row["id"]),
                "snapshot_date": FROZEN_NOW.date(),
                "now_cost": int(row["now_cost"]),
                "selected_by_percent": row["selected_by_percent"],
                "transfers_in_event": 1000,
                "transfers_out_event": 200,
            }
            for row in players[:15]
        ],
        "ingest_runs": [
            {
                "id": 1,
                "job": "bootstrap",
                "started_at": FROZEN_NOW,
                "finished_at": FROZEN_NOW,
                "ok": True,
                "detail": "synthetic",
            }
        ],
        "data_versions": [
            {"id": 1, "ingest_run_id": 1, "next_gw": NEXT_GW, "created_at": FROZEN_NOW}
        ],
    }


def squad_ids() -> list[int]:
    return [row[0] for row in SQUAD]


def _team(team_id: int, name: str, short: str) -> dict[str, Any]:
    return {
        "season_id": SEASON,
        "id": team_id,
        "code": 100 + team_id,
        "name": name,
        "short_name": short,
        "strength_overall_home": 3,
        "strength_overall_away": 3,
        "strength_attack_home": 0,
        "strength_attack_away": 0,
        "strength_defence_home": 3,
        "strength_defence_away": 3,
        "updated_at": FROZEN_NOW,
    }


def _gw(
    gw_id: int,
    name: str,
    deadline: datetime,
    *,
    finished: bool = False,
    previous: bool = False,
    nxt: bool = False,
) -> dict[str, Any]:
    return {
        "season_id": SEASON,
        "id": gw_id,
        "name": name,
        "deadline_time": deadline,
        "is_current": False,
        "is_next": nxt,
        "is_previous": previous,
        "finished": finished,
        "data_checked": finished,
        "average_entry_score": 48 if finished else None,
        "highest_score": 90 if finished else None,
        "most_captained": CAPTAIN_ID if finished else None,
    }


def _player(
    player_id: int,
    team_id: int,
    position_id: int,
    name: str,
    cost: int,
    own: float,
) -> dict[str, Any]:
    return {
        "season_id": SEASON,
        "id": player_id,
        "code": 1000 + player_id,
        "web_name": name,
        "first_name": name,
        "second_name": name,
        "team_id": team_id,
        "position_id": position_id,
        "status": "a",
        "news": "",
        "chance_of_playing_this_round": None,
        "chance_of_playing_next_round": None,
        "now_cost": cost,
        "cost_change_start": 0,
        "cost_change_event": 0,
        "selected_by_percent": own,
        "transfers_in_event": 1000,
        "transfers_out_event": 200,
        "transfers_in": 5000,
        "transfers_out": 1000,
        "event_points": 6,
        "goals_scored": 1 if position_id == 4 else 0,
        "assists": 1 if position_id == 3 else 0,
        "clean_sheets": 1 if position_id <= 2 else 0,
        "bonus": 1,
        "bps": 20,
        "defensive_contribution": 4,
        "ict_index": 5.0,
        "penalties_order": 1 if player_id == CAPTAIN_ID else None,
        "corners_and_indirect_freekicks_order": None,
        "direct_freekicks_order": None,
        "form": 4.5,
        "points_per_game": 4.5,
        "total_points": 40,
        "minutes": 600,
        "history_minutes": 600,
        "starts": 8,
        "expected_goals": 1.2,
        "expected_assists": 0.4,
        "expected_goal_involvements": 1.6,
        "expected_goals_conceded": 1.0,
        "ep_next": 5.0,
        "can_transact": True,
        "removed": False,
        "updated_at": FROZEN_NOW,
    }


def _rest(start: int) -> list[dict[str, Any]]:
    rows = []
    for player_id in range(start, 41):
        team_id = ((player_id - 1) % 20) + 1
        rows.append(_player(player_id, team_id, 3, f"P{player_id}", 55, 1.0))
    return rows


def _metric(player_id: int) -> dict[str, Any]:
    return {
        "season_id": SEASON,
        "player_id": player_id,
        "computed_for_gw": NEXT_GW,
        "horizon": 1,
        "form_raw": 0.5,
        "form_score": 0.5,
        "fixture_raw": 0.6,
        "fixture_score": 0.6,
        "home_raw": 0.5,
        "home_score": 0.5,
        "xgi_raw": 0.4,
        "xgi_score": 0.4,
        "value_raw": 0.3,
        "value_score": 0.3,
        "minutes_raw": 0.8,
        "minutes_score": 0.8,
        "trend_raw": 0.1,
        "trend_score": 0.1,
        "fixture_count": 1,
        "availability": 1.0,
        "computed_at": FROZEN_NOW,
    }


def _match(player_id: int, team_id: int) -> dict[str, Any]:
    return {
        "season_id": SEASON,
        "player_id": player_id,
        "fixture_id": 800 + player_id,
        "round": 8,
        "opponent_team": 1 if team_id != 1 else 2,
        "was_home": True,
        "minutes": 90,
        "starts": 1,
        "total_points": 6,
        "goals_scored": 0,
        "assists": 0,
        "clean_sheets": 0,
        "goals_conceded": 1,
        "bonus": 0,
        "bps": 15,
        "saves": 0,
        "defensive_contribution": 2,
        "expected_goals": 0.2,
        "expected_assists": 0.1,
        "expected_goal_involvements": 0.3,
        "expected_goals_conceded": 1.0,
        "ict_index": 3.0,
        "value": 55,
        "selected": 100000,
        "transfers_balance": 100,
    }


def _fixtures(deadline: datetime) -> list[dict[str, Any]]:
    rows = []
    fixture_id = 1
    for event, kickoff in ((9, deadline), (10, deadline + timedelta(days=7))):
        homes = list(range(1, 21, 2))
        aways = list(range(2, 21, 2))
        if event == 10:
            homes, aways = aways, homes
        for home, away in zip(homes, aways, strict=True):
            rows.append(_fixture(fixture_id, event, kickoff, home, away))
            fixture_id += 1
    rows.append(_fixture(900, None, None, 1, 2))
    return rows


def _fixture(
    fixture_id: int,
    event: int | None,
    kickoff: datetime | None,
    home: int,
    away: int,
) -> dict[str, Any]:
    return {
        "season_id": SEASON,
        "id": fixture_id,
        "event": event,
        "kickoff_time": kickoff,
        "team_h": home,
        "team_a": away,
        "team_h_difficulty": 3,
        "team_a_difficulty": 3,
        "team_h_score": None,
        "team_a_score": None,
        "started": False,
        "finished": False,
        "updated_at": FROZEN_NOW,
    }
