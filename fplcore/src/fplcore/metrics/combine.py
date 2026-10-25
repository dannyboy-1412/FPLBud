from __future__ import annotations

import math

from fplcore.constants import (
    ALL_METRICS,
    DEFAULT_WEIGHTS,
    PROJ_A_FALLBACK,
    PROJ_B_FALLBACK,
)


def renormalise_weights(weights: dict[str, float] | None) -> dict[str, float]:
    merged = {**DEFAULT_WEIGHTS, **(weights or {})}
    total = sum(max(float(merged.get(key, 0.0)), 0.0) for key in ALL_METRICS)
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {key: max(float(merged.get(key, 0.0)), 0.0) / total for key in ALL_METRICS}


def combined_score(scores: dict[str, float], weights: dict[str, float] | None) -> float:
    w = renormalise_weights(weights)
    return sum(w[key] * float(scores.get(key, 0.0) or 0.0) for key in ALL_METRICS)


def availability(
    *,
    chance_of_playing_next_round: int | None,
    status: str,
    k: int,
) -> float:
    """k is 1-based index of the upcoming gameweek in the horizon."""
    if status == "u":
        return 0.0
    if chance_of_playing_next_round is None:
        cop = 1.0 if status == "a" else 0.0
    else:
        cop = chance_of_playing_next_round / 100.0
    return 1.0 - (1.0 - cop) * (0.5 ** (k - 1))


def playing_share(minutes_score: float, season_minutes: int | None = None) -> float:
    """How much of a projection a player keeps once start rate is applied.

    Injury status is handled separately. A player who has not played this
    season keeps none of it: an easy fixture is not evidence they will start.
    ``season_minutes`` of None means that fact is unknown, so only the recent
    start rate is used.
    """
    if season_minutes is not None and int(season_minutes) <= 0:
        return 0.0
    return min(max(float(minutes_score), 0.0), 1.0)


def projected_points(
    *,
    score: float,
    fixture_count: int,
    avail: float,
    minutes: float = 1.0,
    a: float = PROJ_A_FALLBACK,
    b: float = PROJ_B_FALLBACK,
) -> float:
    if fixture_count <= 0:
        return 0.0
    playing = min(max(float(minutes), 0.0), 1.0)
    return fixture_count * avail * playing * (a + b * score)


def poisson_clean_sheet(xgc90: float) -> float:
    return math.exp(-max(xgc90, 0.0))
