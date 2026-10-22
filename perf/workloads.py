"""Offline season built from the frozen FPL samples.

The suite never opens Postgres and never calls the public FPL API. History
rows and daily snapshots are synthesised from the bootstrap totals so the
metric code sees a full-size frame.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from fplcore.db.repos import season_id_from_bootstrap
from fplcore.models import (
    BootstrapStatic,
    Element,
    ElementSummary,
    Entry,
    EntryHistory,
    Fixture,
    PicksPayload,
    TransferRow,
)
from fplcore.optimise import PlayerOpt
from fplcore.team_import import TeamSnapshot, build_snapshot, merged_from_payloads

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
AS_OF = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)

_SAMPLE_FILES = (
    "bootstrap-static.json",
    "fixtures.json",
    "entry.json",
    "picks.json",
    "history.json",
    "transfers.json",
    "element-summary.json",
)


@dataclass
class World:
    dataset: str
    bootstrap_text: str
    fixtures_text: str
    entry_text: str
    picks_text: str
    history_text: str
    transfers_text: str
    summary_text: str
    bootstrap: BootstrapStatic
    fixtures: list[Fixture]
    players: pd.DataFrame
    history: pd.DataFrame
    fixtures_frame: pd.DataFrame
    snapshots: pd.DataFrame
    next_gw: int
    last_rounds: list[int]
    manager_count: int
    hours_since_deadline: float
    season_id: str
    cards: list[dict[str, Any]]
    rows_by_id: dict[int, dict[str, Any]]
    yesterday: dict[int, dict[str, Any]]
    elements_by_id: dict[int, Element]
    opt_players: list[PlayerOpt]
    squad_ids: list[int]
    starters: list[int]
    bench: list[int]
    positions: dict[int, int]
    snapshot: TeamSnapshot
    entry: Entry
    entry_history: EntryHistory
    transfers: list[TransferRow]
    summary: ElementSummary
    gameweeks: list[dict[str, Any]]
    gameweeks_by_id: dict[int, dict[str, Any]]
    picks_by_event: dict[int, dict[str, Any]]
    captain_points: dict[tuple[int, int], int]
    captain_names: dict[int, str]
    most_captained: dict[int, int | None]
    team_names: dict[int, str]
    fixtures_by_team: dict[int, list[dict[str, Any]]]
    as_of: datetime


def load() -> World:
    """Build an offline season from the frozen samples."""
    texts = _sample_texts()
    bootstrap = BootstrapStatic.model_validate_json(texts["bootstrap-static.json"])
    fixtures = [Fixture.model_validate(row) for row in json.loads(texts["fixtures.json"])]
    entry = Entry.model_validate_json(texts["entry.json"])
    picks = PicksPayload.model_validate_json(texts["picks.json"])
    history = EntryHistory.model_validate_json(texts["history.json"])
    transfers = [TransferRow.model_validate(row) for row in json.loads(texts["transfers.json"])]
    summary = ElementSummary.model_validate_json(texts["element-summary.json"])

    if not bootstrap.elements or not bootstrap.events:
        raise RuntimeError("bootstrap sample has no players or gameweeks")

    next_gw = _next_gw(bootstrap)
    last_rounds = list(range(max(1, next_gw - 5), next_gw)) or [max(1, next_gw - 1)]
    players = _players_frame(bootstrap.elements)
    history_frame = _history_frame(bootstrap.elements, last_rounds)
    fixtures_frame = _fixtures_frame(fixtures)
    snapshots = _snapshots_frame(bootstrap.elements)
    if history_frame.empty or fixtures_frame.empty:
        raise RuntimeError("sample season has no history or fixtures to score")

    elements_by_id = {element.id: element for element in bootstrap.elements}
    squad_ids = _select_squad(bootstrap.elements)
    starters, bench, positions = _xi_and_bench(squad_ids, elements_by_id)
    cards = _cards(bootstrap)
    rows_by_id = {int(card["id"]): card for card in cards}
    team_names = {team.id: team.short_name for team in bootstrap.teams}
    captain_id = starters[0]
    gameweeks = [_gameweek(event) for event in bootstrap.events]
    merged = merged_from_payloads(entry, picks, history, transfers)
    season_id = season_id_from_bootstrap(bootstrap)

    return World(
        dataset=f"{len(bootstrap.elements)} players, {len(fixtures)} fixtures, next gameweek {next_gw}",
        bootstrap_text=texts["bootstrap-static.json"],
        fixtures_text=texts["fixtures.json"],
        entry_text=texts["entry.json"],
        picks_text=texts["picks.json"],
        history_text=texts["history.json"],
        transfers_text=texts["transfers.json"],
        summary_text=texts["element-summary.json"],
        bootstrap=bootstrap,
        fixtures=fixtures,
        players=players,
        history=history_frame,
        fixtures_frame=fixtures_frame,
        snapshots=snapshots,
        next_gw=next_gw,
        last_rounds=last_rounds,
        manager_count=bootstrap.total_players or len(bootstrap.elements),
        hours_since_deadline=24.0,
        season_id=season_id,
        cards=cards,
        rows_by_id=rows_by_id,
        yesterday=_yesterday(bootstrap.elements),
        elements_by_id=elements_by_id,
        opt_players=_opt_players(bootstrap.elements, set(squad_ids)),
        squad_ids=squad_ids,
        starters=starters,
        bench=bench,
        positions=positions,
        snapshot=build_snapshot(
            merged=merged,
            players=elements_by_id,
            chip_windows=bootstrap.chips,
            season_id=season_id,
            max_extra_free_transfers=bootstrap.game_settings.max_extra_free_transfers,
        ),
        entry=entry,
        entry_history=history,
        transfers=transfers,
        summary=summary,
        gameweeks=gameweeks,
        gameweeks_by_id={int(row["id"]): row for row in gameweeks},
        picks_by_event={
            row.event: {
                "picks": [{"element": captain_id, "is_captain": True, "multiplier": 2}],
                "active_chip": None,
            }
            for row in history.current
        },
        captain_points={(captain_id, row.event): 6 for row in history.current},
        captain_names={captain_id: elements_by_id[captain_id].web_name},
        most_captained={event.id: event.most_captained for event in bootstrap.events},
        team_names=team_names,
        fixtures_by_team=_fixtures_by_team(fixtures, next_gw),
        as_of=AS_OF,
    )


def _sample_texts() -> dict[str, str]:
    missing = [name for name in _SAMPLE_FILES if not (SAMPLES / name).is_file()]
    if missing:
        raise FileNotFoundError(f"performance samples missing: {', '.join(missing)}")
    return {name: (SAMPLES / name).read_text(encoding="utf-8") for name in _SAMPLE_FILES}


def _next_gw(bootstrap: BootstrapStatic) -> int:
    flagged = next((event for event in bootstrap.events if event.is_next), None)
    if flagged is not None:
        return flagged.id
    return bootstrap.events[-1].id


def _players_frame(elements: list[Element]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [element.id for element in elements],
            "team_id": [element.team for element in elements],
            "position_id": [element.element_type for element in elements],
            "form": [element.form for element in elements],
            "points_per_game": [element.points_per_game for element in elements],
            "now_cost": [element.now_cost for element in elements],
            "minutes": [element.minutes for element in elements],
            "starts": [element.starts for element in elements],
            "status": [element.status for element in elements],
            "chance_of_playing_next_round": [
                element.chance_of_playing_next_round for element in elements
            ],
            "transfers_in_event": [element.transfers_in_event for element in elements],
            "transfers_out_event": [element.transfers_out_event for element in elements],
            "expected_goals_per_90": [element.expected_goals_per_90 for element in elements],
            "expected_assists_per_90": [element.expected_assists_per_90 for element in elements],
            "expected_goals_conceded_per_90": [
                element.expected_goals_conceded_per_90 for element in elements
            ],
        }
    )


def _history_frame(elements: list[Element], rounds: list[int]) -> pd.DataFrame:
    share = len(rounds)
    player_id: list[int] = []
    round_id: list[int] = []
    minutes: list[int] = []
    starts: list[int] = []
    points: list[int] = []
    xg: list[float] = []
    xa: list[float] = []
    xgc: list[float] = []
    for element in elements:
        if element.minutes <= 0:
            continue
        minute_share = min(90, max(element.minutes // share, 1))
        for rnd in rounds:
            player_id.append(element.id)
            round_id.append(rnd)
            minutes.append(minute_share)
            starts.append(1 if minute_share >= 60 else 0)
            points.append(element.total_points // share)
            xg.append(element.expected_goals / share)
            xa.append(element.expected_assists / share)
            xgc.append(element.expected_goals_conceded / share)
    return pd.DataFrame(
        {
            "player_id": player_id,
            "round": round_id,
            "minutes": minutes,
            "starts": starts,
            "total_points": points,
            "expected_goals": xg,
            "expected_assists": xa,
            "expected_goals_conceded": xgc,
        }
    )


def _fixtures_frame(fixtures: list[Fixture]) -> pd.DataFrame:
    scheduled = [fixture for fixture in fixtures if fixture.event is not None]
    return pd.DataFrame(
        {
            "id": [fixture.id for fixture in scheduled],
            "event": [int(fixture.event) for fixture in scheduled],
            "team_h": [fixture.team_h for fixture in scheduled],
            "team_a": [fixture.team_a for fixture in scheduled],
            "team_h_difficulty": [fixture.team_h_difficulty for fixture in scheduled],
            "team_a_difficulty": [fixture.team_a_difficulty for fixture in scheduled],
        }
    )


def _snapshots_frame(elements: list[Element]) -> pd.DataFrame:
    player_id: list[int] = []
    snapshot_date: list[int] = []
    now_cost: list[int] = []
    for element in elements:
        for day in range(8):
            player_id.append(element.id)
            snapshot_date.append(day)
            now_cost.append(element.now_cost if day < 7 else element.now_cost + 1)
    return pd.DataFrame(
        {"player_id": player_id, "snapshot_date": snapshot_date, "now_cost": now_cost}
    )


def _select_squad(elements: list[Element]) -> list[int]:
    needed = {1: 2, 2: 5, 3: 5, 4: 3}
    per_club: dict[int, int] = {}
    chosen: list[int] = []
    for element in sorted(elements, key=lambda item: (item.now_cost, item.id)):
        position = element.element_type
        if needed.get(position, 0) <= 0:
            continue
        if per_club.get(element.team, 0) >= 3:
            continue
        if element.removed or not element.can_transact:
            continue
        chosen.append(element.id)
        needed[position] -= 1
        per_club[element.team] = per_club.get(element.team, 0) + 1
        if not any(needed.values()):
            return chosen
    still = {position: count for position, count in needed.items() if count}
    raise RuntimeError(f"sample cannot fill a squad, still need {still}")


def _xi_and_bench(
    squad_ids: list[int], elements_by_id: dict[int, Element]
) -> tuple[list[int], list[int], dict[int, int]]:
    by_pos: dict[int, list[int]] = {1: [], 2: [], 3: [], 4: []}
    for player_id in squad_ids:
        by_pos[elements_by_id[player_id].element_type].append(player_id)
    starters = by_pos[1][:1] + by_pos[2][:4] + by_pos[3][:4] + by_pos[4][:2]
    bench = [by_pos[1][1], by_pos[2][4], by_pos[3][4], by_pos[4][2]]
    positions = {player_id: elements_by_id[player_id].element_type for player_id in squad_ids}
    if len(starters) != 11 or len(bench) != 4:
        raise RuntimeError("sample squad does not split into a legal XI and bench")
    return starters, bench, positions


def _cards(bootstrap: BootstrapStatic) -> list[dict[str, Any]]:
    teams = {team.id: team.short_name for team in bootstrap.teams}
    cards: list[dict[str, Any]] = []
    for element in bootstrap.elements:
        cards.append(
            {
                "id": element.id,
                "web_name": element.web_name,
                "team_id": element.team,
                "team_short": teams.get(element.team, ""),
                "position_id": element.element_type,
                "now_cost": element.now_cost,
                "selected_by_percent": element.selected_by_percent,
                "transfers_in_event": element.transfers_in_event,
                "transfers_out_event": element.transfers_out_event,
                "cost_change_event": element.cost_change_event,
                "cost_change_start": element.cost_change_start,
                "minutes": element.minutes,
                "starts": element.starts,
                "goals_scored": element.goals_scored,
                "assists": element.assists,
                "expected_goals": element.expected_goals,
                "expected_goal_involvements": element.expected_goal_involvements,
                "bonus": element.bonus,
                "bps": element.bps,
                "form": element.form,
                "penalties_order": element.penalties_order,
                "corners_and_indirect_freekicks_order": element.corners_and_indirect_freekicks_order,
                "direct_freekicks_order": element.direct_freekicks_order,
                "recent_minutes": element.minutes,
                "recent_points": element.total_points,
                "recent_xgi": element.expected_goal_involvements,
                "recent_dc": element.defensive_contribution or 0,
                "dc_starts": element.starts,
                "dc_hits": element.starts // 2,
                "proj": float(element.ep_next or element.form or 0),
                "status": element.status,
                "chance_of_playing_next_round": element.chance_of_playing_next_round,
                "form_score": min(float(element.form) / 10.0, 1.0),
                "fixture_score": 0.5,
                "home_score": 0.5,
                "xgi_score": 0.5,
                "value_score": 0.4,
                "minutes_score": 0.7 if element.minutes else 0.0,
                "trend_score": 0.5,
                "fixture_count": 0 if element.status == "u" else 1,
            }
        )
    return cards


def _yesterday(elements: list[Element]) -> dict[int, dict[str, Any]]:
    return {
        element.id: {
            "transfers_in_event": element.transfers_in_event,
            "transfers_out_event": element.transfers_out_event,
            "now_cost": max(element.now_cost - 1, 0),
        }
        for element in elements
    }


def _opt_players(elements: list[Element], squad_ids: set[int]) -> list[PlayerOpt]:
    players: list[PlayerOpt] = []
    for element in elements:
        if element.element_type not in {1, 2, 3, 4}:
            continue
        if element.removed and element.id not in squad_ids:
            continue
        base = float(element.ep_next or 0) or float(element.form or 0) or 2.0
        players.append(
            PlayerOpt(
                id=element.id,
                web_name=element.web_name,
                team_id=element.team,
                position_id=element.element_type,
                cost=max(element.now_cost, 1),
                sell=max(element.now_cost, 1),
                in_squad=element.id in squad_ids,
                can_in=element.can_transact and not element.removed,
                locked=False,
                proj=[base, base * 0.95, base * 0.9, base * 0.85, base * 0.8],
                scores_gw1={
                    "form": 0.5,
                    "fixture": 0.5,
                    "home": 0.5,
                    "xgi": 0.5,
                    "value": 0.4,
                    "minutes": 0.6,
                    "trend": 0.3,
                },
            )
        )
    present = {player.id for player in players}
    missing = squad_ids - present
    if missing:
        raise RuntimeError(f"squad players missing from the optimiser pool: {sorted(missing)}")
    return players


def _gameweek(event: Any) -> dict[str, Any]:
    return {
        "id": event.id,
        "is_next": event.is_next,
        "is_current": event.is_current,
        "deadline_time": event.deadline_time,
        "average_entry_score": event.average_entry_score,
        "highest_score": event.highest_score,
    }


def _fixtures_by_team(fixtures: list[Fixture], gameweek: int) -> dict[int, list[dict[str, Any]]]:
    by_team: dict[int, list[dict[str, Any]]] = {}
    for fixture in fixtures:
        if fixture.event != gameweek:
            continue
        by_team.setdefault(fixture.team_h, []).append(
            {"opponent": fixture.team_a, "home": True, "difficulty": fixture.team_h_difficulty}
        )
        by_team.setdefault(fixture.team_a, []).append(
            {"opponent": fixture.team_h, "home": False, "difficulty": fixture.team_a_difficulty}
        )
    return by_team
