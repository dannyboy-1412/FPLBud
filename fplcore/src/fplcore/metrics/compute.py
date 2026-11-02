from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fplcore.constants import (
    FIXTURE_FORM_WEIGHT,
    FORM_EWMA_ALPHA,
    GOAL_POINTS,
    MINUTES_EWMA_ALPHA,
    START_POINTS_FLOOR,
    TEAM_FORM_MATCHES,
    TEAM_FORM_PRIOR_MATCHES,
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


def _position_mean(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0
    return float(finite.mean())


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
    played = agg["minutes"].clip(lower=1)

    def per90(column: str) -> pd.Series:
        return players["id"].map(agg[column].astype(float) * 90.0 / played)

    recent90_xg = per90("xg").fillna(0.0)
    recent90_xa = per90("xa").fillna(0.0)
    recent90_xgc = per90("xgc").fillna(season_xgc90)

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
            prior_g[mask] = _position_mean(xp90_goal[mask])
            prior_a[mask] = _position_mean(xp90_assist[mask])
            prior_gc[mask] = _position_mean(xp90_gc[mask])

    xg90 = shrink(xp90_goal, prior_g)
    xa90 = shrink(xp90_assist, prior_a)
    xgc90 = shrink(xp90_gc, prior_gc)

    goal_pts = players["position_id"].map(GOAL_POINTS).astype(float).to_numpy()
    raw = goal_pts * xg90 + 3.0 * xa90
    defenderish = players["position_id"].isin([1, 2]).to_numpy()
    raw = np.where(defenderish, raw + 4.0 * np.exp(-np.clip(xgc90, 0, None)), raw)
    return pd.Series(raw, index=players.index).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _ewma_weights(count: int, alpha: float) -> list[float]:
    if count <= 0:
        return []
    decay = 1.0 - alpha
    return [decay ** (count - 1 - index) * (1.0 if index == 0 else alpha) for index in range(count)]


def _minutes_from_matches(starts: list[float], minutes: list[float]) -> float:
    weights = _ewma_weights(len(starts), MINUTES_EWMA_ALPHA)
    start_rate = sum(weight * started for weight, started in zip(weights, starts, strict=True))
    start_weight = sum(weight for weight, started in zip(weights, starts, strict=True) if started > 0)
    if start_weight <= 0:
        return 0.0
    complete = (
        sum(
            weight * (played / 90.0)
            for weight, started, played in zip(weights, starts, minutes, strict=True)
            if started > 0
        )
        / start_weight
    )
    played_share = START_POINTS_FLOOR + (1.0 - START_POINTS_FLOOR) * complete
    return min(max(start_rate * played_share, 0.0), 1.0)


def compute_minutes_raw(players: pd.DataFrame, history: pd.DataFrame, last_team_matches: int = 6) -> pd.Series:
    """Recent starts count more than a flat six-game average.

    A starter who is taken off after 70 minutes keeps the appearance points
    and most of the returns, so that match does not cut the projection in half.
    """
    if (
        history.empty
        or not {"player_id", "round", "starts", "minutes"} <= set(history.columns)
    ):
        return pd.Series(0.0, index=players.index)
    recent = history.sort_values("round").groupby("player_id").tail(last_team_matches)
    by_id: dict[int, float] = {}
    for player_id, group in recent.groupby("player_id"):
        ordered = group.sort_values("round")
        started = ordered["starts"].astype(float).clip(lower=0, upper=1).tolist()
        played = ordered["minutes"].astype(float).clip(lower=0, upper=90).tolist()
        by_id[int(player_id)] = _minutes_from_matches(started, played)
    return players["id"].map(by_id).fillna(0.0).astype(float).clip(0, 1)


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


def _empty_ratings() -> pd.DataFrame:
    return pd.DataFrame(columns=["team_id", "xg_for", "xg_against", "matches"])


def _history_matches(history: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    needed = {"player_id", "round", "opponent_team", "expected_goals"}
    if history.empty or not needed <= set(history.columns):
        return pd.DataFrame(columns=["team_id", "round", "opponent_team", "xg_for", "xg_against"])
    sides = history
    if "team_id" not in sides.columns:
        if players.empty or not {"id", "team_id"} <= set(players.columns):
            return pd.DataFrame(columns=["team_id", "round", "opponent_team", "xg_for", "xg_against"])
        sides = history.merge(players[["id", "team_id"]], left_on="player_id", right_on="id", how="inner")
    sides = sides.dropna(subset=["team_id", "round", "opponent_team"])
    if sides.empty:
        return pd.DataFrame(columns=["team_id", "round", "opponent_team", "xg_for", "xg_against"])
    sides = sides.copy()
    sides["team_id"] = sides["team_id"].astype(int)
    sides["round"] = sides["round"].astype(int)
    sides["opponent_team"] = sides["opponent_team"].astype(int)
    sides["expected_goals"] = pd.to_numeric(sides["expected_goals"], errors="coerce").fillna(0.0)
    grouped = (
        sides.groupby(["team_id", "round", "opponent_team"], as_index=False)["expected_goals"]
        .sum()
        .rename(columns={"expected_goals": "xg_for"})
    )
    flipped = grouped.rename(
        columns={"team_id": "opponent_team", "opponent_team": "team_id", "xg_for": "xg_against"}
    )
    return grouped.merge(flipped, on=["team_id", "round", "opponent_team"], how="inner")


def _score_matches(fixtures: pd.DataFrame) -> pd.DataFrame:
    needed = {"event", "team_h", "team_a", "team_h_score", "team_a_score"}
    columns = ["team_id", "round", "opponent_team", "xg_for", "xg_against"]
    if fixtures.empty or not needed <= set(fixtures.columns):
        return pd.DataFrame(columns=columns)
    played = fixtures.dropna(subset=["event", "team_h_score", "team_a_score"])
    if "finished" in played.columns:
        played = played[played["finished"].fillna(False).astype(bool)]
    rows: list[dict[str, float | int]] = []
    for fixture in played.itertuples(index=False):
        event = int(fixture.event)
        home = int(fixture.team_h)
        away = int(fixture.team_a)
        home_goals = float(fixture.team_h_score)
        away_goals = float(fixture.team_a_score)
        rows.append(
            {
                "team_id": home,
                "round": event,
                "opponent_team": away,
                "xg_for": home_goals,
                "xg_against": away_goals,
            }
        )
        rows.append(
            {
                "team_id": away,
                "round": event,
                "opponent_team": home,
                "xg_for": away_goals,
                "xg_against": home_goals,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _finished_matches(history: pd.DataFrame, fixtures: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    from_history = _history_matches(history, players)
    from_scores = _score_matches(fixtures)
    if from_history.empty:
        return from_scores
    if from_scores.empty:
        return from_history
    usable = from_history[(from_history["xg_for"] > 0) | (from_history["xg_against"] > 0)].copy()
    usable["key"] = list(
        zip(
            usable["team_id"].astype(int),
            usable["round"].astype(int),
            usable["opponent_team"].astype(int),
            strict=True,
        )
    )
    covered = set(usable["key"])
    scores = from_scores.copy()
    scores["key"] = list(
        zip(
            scores["team_id"].astype(int),
            scores["round"].astype(int),
            scores["opponent_team"].astype(int),
            strict=True,
        )
    )
    scores = scores[~scores["key"].isin(covered)]
    return pd.concat(
        [usable.drop(columns="key"), scores.drop(columns="key")],
        ignore_index=True,
    )


def team_form_ratings(history: pd.DataFrame, fixtures: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    """Shrunk xG for and against per team over its last finished matches.

    xG is the sum of the players' expected goals in that match. A match with
    no xG falls back to the final score. An empty frame means there is nothing
    finished to rate, so fixture ease stays on the FDR alone.
    """
    matches = _finished_matches(history, fixtures, players)
    if matches.empty:
        return _empty_ratings()
    recent = matches.sort_values("round").groupby("team_id", as_index=False).tail(TEAM_FORM_MATCHES)
    totals = recent.groupby("team_id", as_index=False).agg(
        xg_for=("xg_for", "sum"),
        xg_against=("xg_against", "sum"),
        matches=("xg_for", "size"),
    )
    played = float(totals["matches"].sum())
    if played <= 0:
        return _empty_ratings()
    league_for = float(totals["xg_for"].sum()) / played
    league_against = float(totals["xg_against"].sum()) / played
    count = totals["matches"].astype(float)
    prior = float(TEAM_FORM_PRIOR_MATCHES)
    totals["xg_for"] = (totals["xg_for"] + prior * league_for) / (count + prior)
    totals["xg_against"] = (totals["xg_against"] + prior * league_against) / (count + prior)
    return totals


def team_form_percentiles(ratings: pd.DataFrame) -> dict[int, tuple[float, float]]:
    """team id to (xG-for percentile, xG-against percentile)."""
    if ratings.empty or "team_id" not in ratings.columns:
        return {}
    attack = ratings["xg_for"].rank(method="average", pct=True)
    conceded = ratings["xg_against"].rank(method="average", pct=True)
    return {
        int(team_id): (float(attack_pct), float(conceded_pct))
        for team_id, attack_pct, conceded_pct in zip(
            ratings["team_id"], attack, conceded, strict=True
        )
    }


def _form_ease(position_id: int, opponent_id: int, form: dict[int, tuple[float, float]]) -> float:
    attack, conceded = form.get(int(opponent_id), (0.5, 0.5))
    if int(position_id) in {1, 2}:
        return 1.0 - attack
    return conceded


def fixture_features_for_gw(
    players: pd.DataFrame,
    fixtures: pd.DataFrame,
    gw: int,
    team_ratings: pd.DataFrame | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    gw_fx = fixtures[fixtures["event"] == gw] if not fixtures.empty and "event" in fixtures.columns else fixtures.iloc[0:0]
    ease = pd.Series(0.0, index=players.index)
    home_share = pd.Series(0.5, index=players.index)
    counts = pd.Series(0, index=players.index, dtype=int)
    if gw_fx.empty:
        return ease, home_share, counts

    form = team_form_percentiles(team_ratings if team_ratings is not None else _empty_ratings())
    have_form = bool(form)
    records: dict[int, list[tuple[float, float, int]]] = {}
    for fixture in gw_fx.itertuples(index=False):
        home = int(fixture.team_h)
        away = int(fixture.team_a)
        records.setdefault(home, []).append(((5 - float(fixture.team_h_difficulty)) / 4.0, 1.0, away))
        records.setdefault(away, []).append(((5 - float(fixture.team_a_difficulty)) / 4.0, 0.0, home))

    for idx, player in players.iterrows():
        rows = records.get(int(player["team_id"]), [])
        counts.loc[idx] = len(rows)
        if not rows:
            ease.loc[idx] = 0.0
            home_share.loc[idx] = 0.5
            continue
        blended: list[float] = []
        for fdr_ease, _home, opponent in rows:
            if not have_form:
                blended.append(fdr_ease)
                continue
            opponent_ease = _form_ease(int(player["position_id"]), opponent, form)
            blended.append((1.0 - FIXTURE_FORM_WEIGHT) * fdr_ease + FIXTURE_FORM_WEIGHT * opponent_ease)
        ease.loc[idx] = float(np.mean(blended))
        home_share.loc[idx] = float(np.mean([row[1] for row in rows]))
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

    ratings = team_form_ratings(history, fixtures, frame)
    rows: list[MetricRow] = []
    for offset in range(6):
        gw = next_gw + offset
        ease, home_share, counts = fixture_features_for_gw(frame, fixtures, gw, ratings)
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
