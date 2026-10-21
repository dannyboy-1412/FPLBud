from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


class FplModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class GameSettings(FplModel):
    squad_squadsize: int = 15
    squad_team_limit: int = 3
    squad_total_spend: int = 1000
    max_extra_free_transfers: int = 4
    transfers_sell_on_fee: float = 0.5


class ChipWindow(FplModel):
    id: int | None = None
    name: str
    number: int | None = None
    start_event: int
    stop_event: int
    chip_type: str | None = None
    overrides: dict[str, Any] | None = None


class ElementType(FplModel):
    id: int
    singular_name_short: str
    squad_select: int
    squad_min_play: int
    squad_max_play: int


class Team(FplModel):
    id: int
    code: int
    name: str
    short_name: str
    strength_overall_home: int = 0
    strength_overall_away: int = 0
    strength_attack_home: int = 0
    strength_attack_away: int = 0
    strength_defence_home: int = 0
    strength_defence_away: int = 0


class Event(FplModel):
    id: int
    name: str
    deadline_time: datetime
    is_current: bool
    is_next: bool
    is_previous: bool
    finished: bool
    data_checked: bool
    average_entry_score: int | None = None
    highest_score: int | None = None
    most_captained: int | None = None


class Element(FplModel):
    id: int
    code: int
    web_name: str
    first_name: str | None = None
    second_name: str | None = None
    team: int
    element_type: int
    status: str
    news: str | None = None
    chance_of_playing_this_round: int | None = None
    chance_of_playing_next_round: int | None = None
    now_cost: int
    cost_change_start: int
    cost_change_event: int
    selected_by_percent: float
    transfers_in_event: int
    transfers_out_event: int
    transfers_in: int = 0
    transfers_out: int = 0
    event_points: int = 0
    goals_scored: int = 0
    assists: int = 0
    clean_sheets: int = 0
    bonus: int = 0
    bps: int = 0
    penalties_order: int | None = None
    corners_and_indirect_freekicks_order: int | None = None
    direct_freekicks_order: int | None = None
    form: float
    points_per_game: float
    total_points: int
    minutes: int
    starts: int
    expected_goals: float
    expected_assists: float
    expected_goal_involvements: float
    expected_goals_conceded: float
    expected_goals_per_90: float = 0.0
    expected_assists_per_90: float = 0.0
    expected_goal_involvements_per_90: float = 0.0
    expected_goals_conceded_per_90: float = 0.0
    ep_next: float | None = None
    can_transact: bool = True
    removed: bool = False
    ict_index: float | None = None
    defensive_contribution: int | None = None

    @field_validator(
        "selected_by_percent",
        "form",
        "points_per_game",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
        "expected_goals_per_90",
        "expected_assists_per_90",
        "expected_goal_involvements_per_90",
        "expected_goals_conceded_per_90",
        "ep_next",
        "ict_index",
        mode="before",
    )
    @classmethod
    def coerce_float(cls, value: Any) -> float | None:
        return _to_float(value)

    @field_validator(
        "penalties_order",
        "corners_and_indirect_freekicks_order",
        "direct_freekicks_order",
        mode="before",
    )
    @classmethod
    def coerce_optional_int(cls, value: Any) -> int | None:
        return _to_int(value)


class BootstrapStatic(FplModel):
    events: list[Event]
    teams: list[Team]
    elements: list[Element]
    element_types: list[ElementType]
    chips: list[ChipWindow] = Field(default_factory=list)
    game_settings: GameSettings = Field(default_factory=GameSettings)
    total_players: int = 0


class Fixture(FplModel):
    id: int
    event: int | None = None
    kickoff_time: datetime | None = None
    team_h: int
    team_a: int
    team_h_difficulty: int
    team_a_difficulty: int
    team_h_score: int | None = None
    team_a_score: int | None = None
    started: bool | None = None
    finished: bool = False


class HistoryRow(FplModel):
    fixture: int
    round: int
    opponent_team: int
    was_home: bool
    minutes: int
    starts: int = 0
    total_points: int
    goals_scored: int = 0
    assists: int = 0
    clean_sheets: int = 0
    goals_conceded: int = 0
    bonus: int = 0
    bps: int = 0
    saves: int = 0
    defensive_contribution: int = 0
    expected_goals: float = 0.0
    expected_assists: float = 0.0
    expected_goal_involvements: float = 0.0
    expected_goals_conceded: float = 0.0
    ict_index: float = 0.0
    value: int
    selected: int = 0
    transfers_balance: int = 0

    @field_validator(
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
        "ict_index",
        mode="before",
    )
    @classmethod
    def coerce_float(cls, value: Any) -> float | None:
        return _to_float(value) or 0.0


class UpcomingFixture(FplModel):
    id: int | None = None
    event: int | None = None
    difficulty: int
    is_home: bool
    month: int | None = None
    kickoff_time: datetime | None = None
    team_h: int | None = None
    team_a: int | None = None


class ElementSummary(FplModel):
    fixtures: list[UpcomingFixture] = Field(default_factory=list)
    history: list[HistoryRow] = Field(default_factory=list)
    history_past: list[dict[str, Any]] = Field(default_factory=list)


class Entry(FplModel):
    id: int
    name: str
    player_first_name: str = ""
    player_last_name: str = ""
    player_region_name: str | None = None
    summary_overall_rank: int | None = None
    current_event: int
    last_deadline_bank: int | None = None
    last_deadline_value: int | None = None
    last_deadline_total_transfers: int | None = None
    leagues: dict[str, Any] | None = None


class Pick(FplModel):
    element: int
    position: int
    multiplier: int = 1
    is_captain: bool = False
    is_vice_captain: bool = False
    element_type: int | None = None


class EntryHistoryRow(FplModel):
    event: int
    points: int = 0
    total_points: int = 0
    rank: int | None = None
    overall_rank: int | None = None
    percentile_rank: int | None = None
    bank: int = 0
    value: int = 0
    event_transfers: int = 0
    event_transfers_cost: int = 0
    points_on_bench: int = 0


class ChipUsed(FplModel):
    name: str
    event: int
    time: datetime | None = None


class EntryHistory(FplModel):
    current: list[EntryHistoryRow] = Field(default_factory=list)
    chips: list[ChipUsed] = Field(default_factory=list)
    past: list[dict[str, Any]] = Field(default_factory=list)


class PicksEventHistory(FplModel):
    event: int | None = None
    points: int | None = None
    total_points: int | None = None
    rank: int | None = None
    overall_rank: int | None = None
    bank: int = 0
    value: int = 0
    event_transfers: int = 0
    event_transfers_cost: int = 0


class PicksPayload(FplModel):
    picks: list[Pick]
    active_chip: str | None = None
    automatic_subs: list[dict[str, Any]] = Field(default_factory=list)
    entry_history: PicksEventHistory


class TransferRow(FplModel):
    element_in: int
    element_in_cost: int
    element_out: int
    element_out_cost: int
    event: int
    time: datetime | None = None


class MergedEntry(FplModel):
    """Cached public entry payload used by team import."""

    entry: Entry
    picks: PicksPayload
    history: EntryHistory
    transfers: list[TransferRow] = Field(default_factory=list)
