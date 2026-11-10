"""Split a player's matches by fixture difficulty and venue. Totals are precomputed."""

from __future__ import annotations

from typing import Any

_BANDS = ("easy", "medium", "hard")
_VENUES = ("home", "away")
_EMPTY = {
    "matches": 0,
    "appearances": 0,
    "minutes": 0,
    "points": 0,
    "points_per_appearance": None,
    "goals": 0,
    "assists": 0,
    "clean_sheets": 0,
    "bonus": 0,
}


def fdr_band(fdr: int) -> str:
    if fdr <= 2:
        return "easy"
    if fdr == 3:
        return "medium"
    return "hard"


def build_player_record(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_fdr = {band: dict(_EMPTY) for band in _BANDS}
    by_venue = {venue: dict(_EMPTY) for venue in _VENUES}
    matches: list[dict[str, Any]] = []
    for row in rows:
        played = int(row["minutes"]) > 0
        band = fdr_band(int(row["fdr"]))
        venue = "home" if row["was_home"] else "away"
        _add(by_fdr[band], row, played)
        _add(by_venue[venue], row, played)
        matches.append(
            {
                "gw": int(row["round"]),
                "opp": row["opponent"],
                "home": bool(row["was_home"]),
                "fdr": int(row["fdr"]),
                "mins": int(row["minutes"]),
                "pts": int(row["total_points"]),
            }
        )
    for bucket in (*by_fdr.values(), *by_venue.values()):
        appearances = int(bucket["appearances"])
        if appearances:
            bucket["points_per_appearance"] = round(int(bucket["points"]) / appearances, 1)
    return {"by_fdr": by_fdr, "by_venue": by_venue, "matches": matches}


def _add(bucket: dict[str, Any], row: dict[str, Any], played: bool) -> None:
    bucket["matches"] += 1
    bucket["minutes"] += int(row["minutes"])
    bucket["points"] += int(row["total_points"])
    bucket["goals"] += int(row["goals_scored"])
    bucket["assists"] += int(row["assists"])
    bucket["clean_sheets"] += int(row["clean_sheets"])
    bucket["bonus"] += int(row["bonus"])
    if played:
        bucket["appearances"] += 1
