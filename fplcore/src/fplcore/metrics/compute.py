from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fplcore.constants import (
    FORM_EWMA_ALPHA,
    GOAL_POINTS,
    TREND_DEADLINE_HOURS_FLOOR,
    XGI_MINUTES_PRIOR,
)


@dataclass(frozen=True)
class MetricRow:
    player_id: int
    computed_for_gw: int
    horizon: int
    form_raw: float
    form_score: float
    fixture_raw: float
    fixture_score: float
    home_raw: float
    home_score: float
    xgi_raw: float
    xgi_score: float
    value_raw: float
    value_score: float
    minutes_raw: float
    minutes_score: float
    trend_raw: float
    trend_score: float
    fixture_count: int
    availability: float


def _ewma_points(points: list[float], alpha: float = FORM_EWMA_ALPHA) -> float:
    if not points:
        return 0.0
    value = points[0]
    for point in points[1:]:
        value = alpha * point + (1 - alpha) * value
    return value


def _percentile_within_position(frame: pd.DataFrame, raw_col: str, eligible: pd.Series) -> pd.Series:
    scores = pd.Series(0.0, index=frame.index)
    for _, group in frame.groupby("position_id"):
        mask = eligible.reindex(group.index).fillna(False).astype(bool)
        if not mask.any():
            continue
        ranks = group.loc[mask, raw_col].rank(method="average", pct=True)
        scores.loc[ranks.index] = ranks
    return scores


def compute_form_raw(players: pd.DataFrame, history: pd.DataFrame, last_rounds: list[int]) -> pd.Series:
    recent = history[history["round"].isin(last_rounds)].copy()
    appearances = recent[recent["minutes"] > 0]
    ewma_map: dict[int, float] = {}
    for player_id, group in appearances.groupby("player_id"):
        pts = group.sort_values("round").tail(5)["total_points"].astype(float).tolist()
        ewma_map[int(player_id)] = _ewma_points(pts)
    ewma = players["id"].map(ewma_map).fillna(0.0)
    form = players["form"].astype(float)
    return 0.5 * form + 0.5 * ewma


def compute_xgi_raw(players: pd.DataFrame, history: pd.DataFrame, last_rounds: list[int]) -> pd.Series:
    season_xg90 = players["expected_goals_per_90"].astype(float)
    season_xa90 = players["expected_assists_per_90"].astype(float)
    season_xgc90 = players["expected_goals_conceded_per_90"].astype(float)

    recent = history[history["round"].isin(last_rounds)]
    agg = recent.groupby("player_id").agg(
        minutes=("minutes", "sum"),
        xg=("expected_goals", "sum"),
        xa=("expected_assists", "sum"),
        xgc=("expected_goals_conceded", "sum"),
    )
    recent90_xg = (agg["xg"] * 90.0 / agg["minutes"].clip(lower=1)).reindex(players["id"]).fillna(0.0)
    recent90_xa = (agg["xa"] * 90.0 / agg["minutes"].clip(lower=1)).reindex(players["id"]).fillna(0.0)
    recent90_xgc = (agg["xgc"] * 90.0 / agg["minutes"].clip(lower=1)).reindex(players["id"]).fillna(season_xgc90)

    xp90_goal = 0.6 * recent90_xg.to_numpy() + 0.4 * season_xg90.to_numpy()
    xp90_assist = 0.6 * recent90_xa.to_numpy() + 0.4 * season_xa90.to_numpy()
    xp90_gc = 0.6 * recent90_xgc.to_numpy() + 0.4 * season_xgc90.to_numpy()
    minutes = players["minutes"].astype(float).to_numpy()

    def shrink(series: np.ndarray, prior: np.ndarray) -> np.ndarray:
        return (minutes * series + XGI_MINUTES_PRIOR * prior) / (minutes + XGI_MINUTES_PRIOR)

    prior_g = np.zeros_like(xp90_goal)
    prior_a = np.zeros_like(xp90_assist)
    prior_gc = np.zeros_like(xp90_gc)
    for pos in players["position_id"].unique():
        mask = (players["position_id"] == pos).to_numpy()
        if mask.any():
            prior_g[mask] = xp90_goal[mask].mean()
            prior_a[mask] = xp90_assist[mask].mean()
            prior_gc[mask] = xp90_gc[mask].mean()

    xg90 = shrink(xp90_goal, prior_g)
    xa90 = shrink(xp90_assist, prior_a)
    xgc90 = shrink(xp90_gc, prior_gc)

    goal_pts = players["position_id"].map(GOAL_POINTS).astype(float).to_numpy()
    raw = goal_pts * xg90 + 3.0 * xa90
    defenderish = players["position_id"].isin([1, 2]).to_numpy()
    raw = np.where(defenderish, raw + 4.0 * np.exp(-np.clip(xgc90, 0, None)), raw)
    return pd.Series(raw, index=players.index)


def compute_minutes_raw(players: pd.DataFrame, history: pd.DataFrame, last_team_matches: int = 6) -> pd.Series:
    recent = history.sort_values("round").groupby("player_id").tail(last_team_matches)
    grouped = recent.groupby("player_id")
    starts = grouped["starts"].sum().reindex(players["id"]).fillna(0.0)
    start_rate = (starts / last_team_matches).clip(0, 1)
    started = recent[recent["starts"] > 0].copy()
    if started.empty:
        complete = pd.Series(0.0, index=players.index)
    else:
        started["complete"] = started["minutes"].clip(upper=90) / 90.0
        mean_complete = started.groupby("player_id")["complete"].mean()
        complete = players["id"].map(mean_complete).fillna(0.0)
    return (start_rate.to_numpy() * complete.to_numpy()).clip(0, 1)


def compute_trend_raw(
    players: pd.DataFrame,
    snapshots: pd.DataFrame,
    *,
    total_players: int,
    hours_since_deadline: float,
) -> pd.Series:
    hours = max(hours_since_deadline, TREND_DEADLINE_HOURS_FLOOR)
    net = (players["transfers_in_event"] - players["transfers_out_event"]).astype(float)
    transfer_rate = net / max(total_players, 1) / hours
    price_delta = pd.Series(0.0, index=players.index)
    if not snapshots.empty:
        latest = snapshots.sort_values("snapshot_date")
        by_player = latest.groupby("player_id")
        first = by_player["now_cost"].first()
        last = by_player["now_cost"].last()
        delta = (last - first).reindex(players["id"]).fillna(0.0)
        price_delta = delta.reset_index(drop=True)
        price_delta.index = players.index
    return transfer_rate.reset_index(drop=True) + price_delta


def fixture_features_for_gw(
    players: pd.DataFrame,
    fixtures: pd.DataFrame,
    gw: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    gw_fx = fixtures[fixtures["event"] == gw]
    ease = pd.Series(0.0, index=players.index)
    home_share = pd.Series(0.5, index=players.index)
    counts = pd.Series(0, index=players.index, dtype=int)
    if gw_fx.empty:
        return ease, home_share, counts

    records: dict[int, list[tuple[float, float]]] = {}
    for _, fx in gw_fx.iterrows():
        records.setdefault(int(fx["team_h"]), []).append(((5 - float(fx["team_h_difficulty"])) / 4.0, 1.0))
        records.setdefault(int(fx["team_a"]), []).append(((5 - float(fx["team_a_difficulty"])) / 4.0, 0.0))

    for idx, player in players.iterrows():
        rows = records.get(int(player["team_id"]), [])
        counts.loc[idx] = len(rows)
        if not rows:
            ease.loc[idx] = 0.0
            home_share.loc[idx] = 0.5
        else:
            ease.loc[idx] = float(np.mean([r[0] for r in rows]))
            home_share.loc[idx] = float(np.mean([r[1] for r in rows]))
    return ease, home_share, counts


def compute_player_metrics(
    *,
    players: pd.DataFrame,
    history: pd.DataFrame,
    fixtures: pd.DataFrame,
    snapshots: pd.DataFrame,
    next_gw: int,
    last_rounds: list[int],
    total_players: int,
    hours_since_deadline: float,
) -> list[MetricRow]:
    """Compute all metric components for next_gw .. next_gw+5, horizon=1."""
    frame = players.copy().reset_index(drop=True)
    frame["form_raw"] = compute_form_raw(frame, history, last_rounds)
    frame["xgi_raw"] = compute_xgi_raw(frame, history, last_rounds)
    frame["value_raw"] = frame["points_per_game"].astype(float) / (frame["now_cost"].astype(float) / 10.0)
    frame["minutes_raw"] = compute_minutes_raw(frame, history)
    frame["trend_raw"] = compute_trend_raw(
        frame, snapshots, total_players=total_players, hours_since_deadline=hours_since_deadline
    )

    recent = history[history["round"].isin(last_rounds)]
    appeared = set(recent[recent["minutes"] > 0]["player_id"].tolist())
    eligible = frame["id"].isin(appeared)

    frame["form_score"] = _percentile_within_position(frame, "form_raw", eligible)
    frame["xgi_score"] = _percentile_within_position(frame, "xgi_raw", eligible)
    frame["value_score"] = _percentile_within_position(frame, "value_raw", eligible)
    frame["trend_score"] = frame["trend_raw"].rank(method="average", pct=True)
    frame.loc[~eligible, ["form_score", "xgi_score", "value_score"]] = 0.0
    frame["minutes_score"] = frame["minutes_raw"].clip(0, 1)

    rows: list[MetricRow] = []
    for offset in range(6):
        gw = next_gw + offset
        ease, home_share, counts = fixture_features_for_gw(frame, fixtures, gw)
        for idx, player in frame.iterrows():
            cop = player.get("chance_of_playing_next_round")
            cop_i = None if pd.isna(cop) else int(cop)
            status = str(player["status"])
            if status == "u":
                avail = 0.0
            elif cop_i is None:
                avail = 1.0 if status == "a" else 0.0
            else:
                avail = cop_i / 100.0
            rows.append(
                MetricRow(
                    player_id=int(player["id"]),
                    computed_for_gw=gw,
                    horizon=1,
                    form_raw=float(player["form_raw"]),
                    form_score=float(player["form_score"]),
                    fixture_raw=float(ease.loc[idx]),
                    fixture_score=float(ease.loc[idx]),
                    home_raw=float(home_share.loc[idx]),
                    home_score=float(home_share.loc[idx]),
                    xgi_raw=float(player["xgi_raw"]),
                    xgi_score=float(player["xgi_score"]),
                    value_raw=float(player["value_raw"]),
                    value_score=float(player["value_score"]),
                    minutes_raw=float(player["minutes_raw"]),
                    minutes_score=float(player["minutes_score"]),
                    trend_raw=float(player["trend_raw"]),
                    trend_score=float(player["trend_score"]),
                    fixture_count=int(counts.loc[idx]),
                    availability=float(avail),
                )
            )
    return rows
