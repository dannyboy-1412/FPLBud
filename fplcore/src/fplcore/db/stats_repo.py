from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from psycopg import Connection
from psycopg.types.json import Json

from fplcore.constants import DC_THRESHOLD
from fplcore.db.repos import current_season_id
from fplcore.gameweeks import pick_started_gameweek, pick_upcoming_gameweek


def total_players(conn: Connection) -> int:
    row = conn.execute(
        "select total_players from seasons where is_current = true limit 1"
    ).fetchone()
    return int(row["total_players"]) if row and row["total_players"] else 0


def season_gameweeks(conn: Connection, season_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "select * from gameweeks where season_id = %s order by id",
        [season_id],
    )
    return [dict(row) for row in rows]


def upcoming_gameweek(conn: Connection, season_id: str, now: datetime | None = None) -> dict[str, Any] | None:
    chosen = pick_upcoming_gameweek(season_gameweeks(conn, season_id), now or datetime.now(UTC))
    return dict(chosen) if chosen is not None else None


def started_gameweek(conn: Connection, season_id: str, now: datetime | None = None) -> dict[str, Any] | None:
    chosen = pick_started_gameweek(season_gameweeks(conn, season_id), now or datetime.now(UTC))
    return dict(chosen) if chosen is not None else None


def next_gw_id(conn: Connection, season_id: str) -> int:
    chosen = upcoming_gameweek(conn, season_id)
    if chosen:
        return int(chosen["id"])
    return 1


def next_gw_metric_rows(conn: Connection, player_ids: list[int] | None = None) -> list[dict[str, Any]]:
    """Metric rows for the next gameweek. Omit player_ids to load the whole field."""
    if player_ids is not None and not player_ids:
        return []
    season = current_season_id(conn)
    next_gw = next_gw_id(conn, season)
    sql = """
        select p.id, p.web_name, p.minutes, p.status, p.chance_of_playing_next_round,
               m.form_score, m.fixture_score, m.home_score, m.xgi_score,
               m.value_score, m.minutes_score, m.trend_score, m.fixture_count
          from players p
          left join player_metrics m
            on m.season_id = p.season_id and m.player_id = p.id
           and m.horizon = 1 and m.computed_for_gw = %s
         where p.season_id = %s
    """
    params: list[Any] = [next_gw, season]
    if player_ids is not None:
        sql += " and p.id = any(%s)"
        params.append(player_ids)
    return [dict(row) for row in conn.execute(sql, params)]


def current_player_rows(conn: Connection, *, position: int | None = None) -> list[dict[str, Any]]:
    season = current_season_id(conn)
    sql = """
        select p.id, p.web_name, p.team_id, t.short_name as team_short, p.position_id,
               p.now_cost, p.selected_by_percent, p.transfers_in_event, p.transfers_out_event,
               p.cost_change_event, p.cost_change_start, p.form, p.event_points,
               p.goals_scored, p.assists, p.clean_sheets, p.bonus, p.bps,
               p.defensive_contribution, p.minutes, p.starts,
               p.expected_goals, p.expected_assists, p.expected_goal_involvements,
               p.penalties_order, p.corners_and_indirect_freekicks_order, p.direct_freekicks_order,
               p.status, p.chance_of_playing_next_round, p.news
          from players p
          join teams t on t.season_id = p.season_id and t.id = p.team_id
         where p.season_id = %s
    """
    params: list[Any] = [season]
    if position:
        sql += " and p.position_id = %s"
        params.append(position)
    return [dict(r) for r in conn.execute(sql, params)]


def snapshot_transfer_rows(conn: Connection) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    season = current_season_id(conn)
    dates = list(
        conn.execute(
            """
            select distinct snapshot_date
              from player_daily_snapshots
             where season_id = %s
             order by snapshot_date desc
             limit 2
            """,
            [season],
        )
    )
    if not dates:
        return {}, {}
    latest = dates[0]["snapshot_date"]
    previous = dates[1]["snapshot_date"] if len(dates) > 1 else None

    def load(day: Any) -> dict[int, dict[str, Any]]:
        rows = conn.execute(
            """
            select player_id, now_cost, transfers_in_event, transfers_out_event
              from player_daily_snapshots
             where season_id = %s and snapshot_date = %s
            """,
            [season, day],
        )
        return {int(r["player_id"]): dict(r) for r in rows}

    today = load(latest)
    yday = load(previous) if previous else {}
    return today, yday


def recent_aggregates(
    conn: Connection, *, last_n: int = 6, position: int | None = None
) -> list[dict[str, Any]]:
    season = current_season_id(conn)
    def_th = DC_THRESHOLD[2]
    mid_th = DC_THRESHOLD[3]
    sql = """
        with latest as (
          select coalesce(max(round), 0) as r
            from player_gameweek_stats
           where season_id = %s
        )
        select p.id, p.web_name, p.team_id, t.short_name as team_short, p.position_id,
               p.now_cost, p.selected_by_percent, p.form, p.minutes, p.starts,
               p.bonus, p.bps, p.goals_scored, p.assists,
               p.expected_goals, p.expected_assists, p.expected_goal_involvements,
               coalesce(sum(g.minutes), 0) as recent_minutes,
               coalesce(sum(g.total_points), 0) as recent_points,
               coalesce(sum(g.starts), 0) as recent_starts,
               coalesce(sum(g.bonus), 0) as recent_bonus,
               coalesce(sum(g.bps), 0) as recent_bps,
               coalesce(sum(g.defensive_contribution), 0) as recent_dc,
               coalesce(sum(g.expected_goal_involvements), 0) as recent_xgi,
               coalesce(sum(
                 case when g.starts > 0
                       and g.defensive_contribution >= (
                         case p.position_id
                           when 2 then %s
                           when 3 then %s
                           when 4 then %s
                           else 999
                         end
                       )
                      then 1 else 0 end
               ), 0) as dc_hits,
               coalesce(sum(case when g.starts > 0 then 1 else 0 end), 0) as dc_starts
          from players p
          join teams t on t.season_id = p.season_id and t.id = p.team_id
          left join player_gameweek_stats g
            on g.season_id = p.season_id and g.player_id = p.id
           and g.round > (select r from latest) - %s
         where p.season_id = %s
    """
    params: list[Any] = [season, def_th, mid_th, mid_th, last_n, season]
    if position:
        sql += " and p.position_id = %s"
        params.append(position)
    sql += """
         group by p.season_id, p.id, t.short_name
    """
    return [dict(r) for r in conn.execute(sql, params)]


def next_event_fixtures(conn: Connection) -> dict[int, list[dict[str, Any]]]:
    season = current_season_id(conn)
    gw = next_gw_id(conn, season)
    rows = conn.execute(
        """
        select f.team_h, f.team_a, f.team_h_difficulty, f.team_a_difficulty,
               th.short_name as home_short, ta.short_name as away_short
          from fixtures f
          join teams th on th.season_id = f.season_id and th.id = f.team_h
          join teams ta on ta.season_id = f.season_id and ta.id = f.team_a
         where f.season_id = %s and f.event = %s
        """,
        [season, gw],
    )
    by_team: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        home = {
            "opponent": row["away_short"],
            "fdr": int(row["team_h_difficulty"]),
            "is_home": True,
        }
        away = {
            "opponent": row["home_short"],
            "fdr": int(row["team_a_difficulty"]),
            "is_home": False,
        }
        by_team.setdefault(int(row["team_h"]), []).append(home)
        by_team.setdefault(int(row["team_a"]), []).append(away)
    return by_team


def gameweek_meta_rows(conn: Connection) -> list[dict[str, Any]]:
    season = current_season_id(conn)
    rows = conn.execute(
        """
        select id, average_entry_score, highest_score, most_captained, finished
          from gameweeks
         where season_id = %s
         order by id
        """,
        [season],
    )
    return [dict(r) for r in rows]


def latest_crowd_captain(conn: Connection) -> dict[str, Any] | None:
    season = current_season_id(conn)
    row = conn.execute(
        """
        select g.id as event, g.most_captained, p.web_name, p.event_points, t.short_name as team_short
          from gameweeks g
          join players p on p.season_id = g.season_id and p.id = g.most_captained
          join teams t on t.season_id = p.season_id and t.id = p.team_id
         where g.season_id = %s and g.most_captained is not null
         order by g.id desc
         limit 1
        """,
        [season],
    ).fetchone()
    return dict(row) if row else None


def player_names(conn: Connection, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    season = current_season_id(conn)
    rows = conn.execute(
        "select id, web_name from players where season_id = %s and id = any(%s)",
        [season, ids],
    )
    return {int(r["id"]): r["web_name"] for r in rows}


def player_round_points(
    conn: Connection, player_ids: list[int], rounds: list[int]
) -> dict[tuple[int, int], int]:
    if not player_ids or not rounds:
        return {}
    season = current_season_id(conn)
    rows = conn.execute(
        """
        select player_id, round, total_points as pts
          from player_gw_points
         where season_id = %s and player_id = any(%s) and round = any(%s)
        """,
        [season, player_ids, rounds],
    )
    return {(int(r["player_id"]), int(r["round"])): int(r["pts"]) for r in rows}


def get_entry_event_picks(conn: Connection, entry_id: int, events: list[int]) -> dict[int, dict[str, Any]]:
    if not events:
        return {}
    rows = conn.execute(
        """
        select event, picks, active_chip
          from entry_event_picks
         where entry_id = %s and event = any(%s)
        """,
        [entry_id, events],
    )
    return {int(r["event"]): {"picks": r["picks"], "active_chip": r["active_chip"]} for r in rows}


def put_entry_event_picks(
    conn: Connection,
    entry_id: int,
    event: int,
    picks: list[dict[str, Any]],
    active_chip: str | None,
) -> None:
    conn.execute(
        """
        insert into entry_event_picks (entry_id, event, picks, active_chip, fetched_at)
        values (%s, %s, %s, %s, now())
        on conflict (entry_id, event) do update set
          picks = excluded.picks, active_chip = excluded.active_chip, fetched_at = now()
        """,
        [entry_id, event, Json(picks), active_chip],
    )


def missing_entry_events(conn: Connection, entry_id: int, events: list[int]) -> list[int]:
    if not events:
        return []
    have = set(get_entry_event_picks(conn, entry_id, events))
    return [event for event in events if event not in have]
