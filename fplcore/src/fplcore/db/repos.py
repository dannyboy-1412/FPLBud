from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Json

from fplcore.constants import (
    AGENT_RUN_KEEP_HOURS,
    DAILY_SNAPSHOT_RETENTION_DAYS,
    ENTRY_CACHE_PRUNE_SECONDS,
    LOG_RETENTION_DAYS,
    MATCH_STATS_RETENTION_ROUNDS,
    METRIC_FORWARD_GWS,
)
from fplcore.metrics.compute import MetricRow
from fplcore.models import BootstrapStatic, ElementSummary, Fixture, HistoryRow
from fplcore.team_import import TeamSnapshot


def season_id_from_bootstrap(bootstrap: BootstrapStatic) -> str:
    years = sorted({event.deadline_time.year for event in bootstrap.events})
    if len(years) >= 2:
        return f"{years[0]}/{str(years[-1])[2:]}"
    year = years[0] if years else datetime.now(UTC).year
    return f"{year}/{(year + 1) % 100:02d}"


def log_ingest_start(conn: Connection, job: str) -> int:
    row = conn.execute(
        "insert into ingest_runs (job) values (%s) returning id", [job]
    ).fetchone()
    return int(row["id"])


def log_ingest_finish(conn: Connection, run_id: int, *, ok: bool, detail: str | None = None) -> None:
    conn.execute(
        "update ingest_runs set finished_at = now(), ok = %s, detail = %s where id = %s",
        [ok, detail, run_id],
    )


def upsert_bootstrap(conn: Connection, bootstrap: BootstrapStatic) -> str:
    sid = season_id_from_bootstrap(bootstrap)
    conn.execute(
        """
        insert into seasons (id, is_current, total_players) values (%s, true, %s)
        on conflict (id) do update set is_current = true, total_players = excluded.total_players
        """,
        [sid, bootstrap.total_players],
    )
    conn.execute("update seasons set is_current = false where id <> %s", [sid])
    with conn.pipeline(), conn.cursor() as cur:
        cur.executemany(
            """
            insert into positions (id, short_name, squad_select, squad_min_play, squad_max_play)
            values (%s, %s, %s, %s, %s)
            on conflict (id) do update set
              short_name = excluded.short_name,
              squad_select = excluded.squad_select,
              squad_min_play = excluded.squad_min_play,
              squad_max_play = excluded.squad_max_play
            """,
            [
                (pos.id, pos.singular_name_short, pos.squad_select, pos.squad_min_play, pos.squad_max_play)
                for pos in bootstrap.element_types
            ],
        )
        cur.executemany(
            """
            insert into teams (
              season_id, id, code, name, short_name,
              strength_overall_home, strength_overall_away,
              strength_attack_home, strength_attack_away,
              strength_defence_home, strength_defence_away, updated_at
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
            on conflict (season_id, id) do update set
              code = excluded.code, name = excluded.name, short_name = excluded.short_name,
              strength_overall_home = excluded.strength_overall_home,
              strength_overall_away = excluded.strength_overall_away,
              updated_at = now()
            """,
            [
                (
                    sid, team.id, team.code, team.name, team.short_name,
                    team.strength_overall_home, team.strength_overall_away,
                    team.strength_attack_home, team.strength_attack_away,
                    team.strength_defence_home, team.strength_defence_away,
                )
                for team in bootstrap.teams
            ],
        )
        cur.executemany(
            """
            insert into gameweeks (
              season_id, id, name, deadline_time, is_current, is_next, is_previous,
              finished, data_checked, average_entry_score, highest_score, most_captained
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (season_id, id) do update set
              name = excluded.name, deadline_time = excluded.deadline_time,
              is_current = excluded.is_current, is_next = excluded.is_next,
              is_previous = excluded.is_previous, finished = excluded.finished,
              data_checked = excluded.data_checked,
              average_entry_score = excluded.average_entry_score,
              highest_score = excluded.highest_score,
              most_captained = excluded.most_captained
            """,
            [
                (
                    sid, event.id, event.name, event.deadline_time, event.is_current,
                    event.is_next, event.is_previous, event.finished, event.data_checked,
                    event.average_entry_score, event.highest_score, event.most_captained,
                )
                for event in bootstrap.events
            ],
        )
        cur.executemany(
            """
            insert into players (
              season_id, id, code, web_name, first_name, second_name, team_id, position_id,
              status, news, chance_of_playing_this_round, chance_of_playing_next_round,
              now_cost, cost_change_start, cost_change_event, selected_by_percent,
              transfers_in_event, transfers_out_event, transfers_in, transfers_out, event_points,
              goals_scored, assists, clean_sheets, bonus, bps, defensive_contribution, ict_index,
              penalties_order, corners_and_indirect_freekicks_order, direct_freekicks_order,
              form, points_per_game, total_points,
              minutes, starts, expected_goals, expected_assists, expected_goal_involvements,
              expected_goals_conceded, ep_next, can_transact, removed, updated_at
            ) values (
              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now()
            )
            on conflict (season_id, id) do update set
              web_name = excluded.web_name, team_id = excluded.team_id, position_id = excluded.position_id,
              status = excluded.status, news = excluded.news,
              chance_of_playing_this_round = excluded.chance_of_playing_this_round,
              chance_of_playing_next_round = excluded.chance_of_playing_next_round,
              now_cost = excluded.now_cost, cost_change_start = excluded.cost_change_start,
              cost_change_event = excluded.cost_change_event,
              selected_by_percent = excluded.selected_by_percent,
              transfers_in_event = excluded.transfers_in_event,
              transfers_out_event = excluded.transfers_out_event,
              transfers_in = excluded.transfers_in, transfers_out = excluded.transfers_out,
              event_points = excluded.event_points, goals_scored = excluded.goals_scored,
              assists = excluded.assists, clean_sheets = excluded.clean_sheets,
              bonus = excluded.bonus, bps = excluded.bps,
              defensive_contribution = excluded.defensive_contribution, ict_index = excluded.ict_index,
              penalties_order = excluded.penalties_order,
              corners_and_indirect_freekicks_order = excluded.corners_and_indirect_freekicks_order,
              direct_freekicks_order = excluded.direct_freekicks_order,
              form = excluded.form, points_per_game = excluded.points_per_game,
              total_points = excluded.total_points, minutes = excluded.minutes, starts = excluded.starts,
              expected_goals = excluded.expected_goals, expected_assists = excluded.expected_assists,
              expected_goal_involvements = excluded.expected_goal_involvements,
              expected_goals_conceded = excluded.expected_goals_conceded,
              ep_next = excluded.ep_next, can_transact = excluded.can_transact,
              removed = excluded.removed, updated_at = now()
            """,
            [
                (
                    sid, el.id, el.code, el.web_name, el.first_name, el.second_name, el.team, el.element_type,
                    el.status, el.news, el.chance_of_playing_this_round, el.chance_of_playing_next_round,
                    el.now_cost, el.cost_change_start, el.cost_change_event, el.selected_by_percent,
                    el.transfers_in_event, el.transfers_out_event, el.transfers_in, el.transfers_out,
                    el.event_points, el.goals_scored, el.assists, el.clean_sheets, el.bonus, el.bps,
                    el.defensive_contribution or 0, el.ict_index,
                    el.penalties_order, el.corners_and_indirect_freekicks_order, el.direct_freekicks_order,
                    el.form, el.points_per_game, el.total_points,
                    el.minutes, el.starts, el.expected_goals, el.expected_assists, el.expected_goal_involvements,
                    el.expected_goals_conceded, el.ep_next, el.can_transact, el.removed,
                )
                for el in bootstrap.elements
            ],
        )
    return sid


def maybe_daily_snapshots(conn: Connection, bootstrap: BootstrapStatic, season_id: str) -> None:
    today = datetime.now(UTC).date()
    existing = conn.execute(
        "select 1 from player_daily_snapshots where season_id = %s and snapshot_date = %s limit 1",
        [season_id, today],
    ).fetchone()
    if existing:
        return
    with conn.pipeline(), conn.cursor() as cur:
        cur.executemany(
            """
            insert into player_daily_snapshots (
              season_id, player_id, snapshot_date, now_cost, selected_by_percent,
              transfers_in_event, transfers_out_event
            ) values (%s,%s,%s,%s,%s,%s,%s)
            on conflict do nothing
            """,
            [
                (
                    season_id, el.id, today, el.now_cost, el.selected_by_percent,
                    el.transfers_in_event, el.transfers_out_event,
                )
                for el in bootstrap.elements
            ],
        )


def upsert_fixtures(conn: Connection, fixtures: list[Fixture], season_id: str) -> None:
    with conn.pipeline(), conn.cursor() as cur:
        cur.executemany(
            """
            insert into fixtures (
              season_id, id, event, kickoff_time, team_h, team_a,
              team_h_difficulty, team_a_difficulty, team_h_score, team_a_score,
              started, finished, updated_at
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
            on conflict (season_id, id) do update set
              event = excluded.event, kickoff_time = excluded.kickoff_time,
              team_h_difficulty = excluded.team_h_difficulty,
              team_a_difficulty = excluded.team_a_difficulty,
              team_h_score = excluded.team_h_score, team_a_score = excluded.team_a_score,
              started = excluded.started, finished = excluded.finished, updated_at = now()
            """,
            [
                (
                    season_id, fx.id, fx.event, fx.kickoff_time, fx.team_h, fx.team_a,
                    fx.team_h_difficulty, fx.team_a_difficulty, fx.team_h_score, fx.team_a_score,
                    fx.started, fx.finished,
                )
                for fx in fixtures
            ],
        )


def synced_history_minutes(conn: Connection, season_id: str) -> dict[int, int]:
    rows = conn.execute(
        """
        select id, history_minutes
          from players
         where season_id = %s and history_minutes is not null
        """,
        [season_id],
    )
    return {int(row["id"]): int(row["history_minutes"]) for row in rows}


def players_needing_history(
    current_minutes: dict[int, int],
    synced_minutes: dict[int, int],
) -> list[int]:
    """Players whose saved match history is behind their current season minutes.

    Someone who has never played is skipped. There is nothing to store, and the
    first minute they play selects them because no sync has been recorded.
    """
    return [
        player_id
        for player_id, minutes in current_minutes.items()
        if minutes != synced_minutes.get(player_id) and (minutes > 0 or player_id in synced_minutes)
    ]


def mark_history_synced(conn: Connection, season_id: str, player_id: int, minutes: int) -> None:
    conn.execute(
        """
        update players
           set history_minutes = %s
         where season_id = %s and id = %s
        """,
        [minutes, season_id, player_id],
    )


def round_points_from_history(history: list[HistoryRow]) -> list[tuple[int, int]]:
    totals: dict[int, int] = {}
    for row in history:
        totals[row.round] = totals.get(row.round, 0) + row.total_points
    return list(totals.items())


def upsert_element_history(conn: Connection, season_id: str, player_id: int, summary: ElementSummary) -> None:
    if not summary.history:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into player_gameweek_stats (
              season_id, player_id, fixture_id, round, opponent_team, was_home, minutes, starts,
              total_points, goals_scored, assists, clean_sheets, goals_conceded, bonus, bps, saves,
              defensive_contribution, expected_goals, expected_assists, expected_goal_involvements,
              expected_goals_conceded, ict_index, value, selected, transfers_balance
            ) values (
              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            on conflict (season_id, player_id, fixture_id) do update set
              minutes = excluded.minutes, starts = excluded.starts, total_points = excluded.total_points,
              goals_scored = excluded.goals_scored, assists = excluded.assists,
              clean_sheets = excluded.clean_sheets, goals_conceded = excluded.goals_conceded,
              bonus = excluded.bonus, bps = excluded.bps, saves = excluded.saves,
              defensive_contribution = excluded.defensive_contribution,
              expected_goals = excluded.expected_goals, expected_assists = excluded.expected_assists,
              expected_goal_involvements = excluded.expected_goal_involvements,
              expected_goals_conceded = excluded.expected_goals_conceded
            """,
            [
                (
                    season_id, player_id, row.fixture, row.round, row.opponent_team, row.was_home,
                    row.minutes, row.starts, row.total_points, row.goals_scored, row.assists,
                    row.clean_sheets, row.goals_conceded, row.bonus, row.bps, row.saves,
                    row.defensive_contribution, row.expected_goals, row.expected_assists,
                    row.expected_goal_involvements, row.expected_goals_conceded, row.ict_index,
                    row.value, row.selected, row.transfers_balance,
                )
                for row in summary.history
            ],
        )
        cur.executemany(
            """
            insert into player_gw_points (season_id, player_id, round, total_points)
            values (%s, %s, %s, %s)
            on conflict (season_id, player_id, round) do update
              set total_points = excluded.total_points
            """,
            [
                (season_id, player_id, rnd, pts)
                for rnd, pts in round_points_from_history(summary.history)
            ],
        )


def replace_metrics(conn: Connection, season_id: str, rows: list[MetricRow]) -> int:
    version = conn.execute(
        """
        insert into data_versions (next_gw, created_at)
        values (
          coalesce((select id from gameweeks where season_id = %s and is_next = true limit 1), 1),
          now()
        )
        returning id
        """,
        [season_id],
    ).fetchone()
    with conn.pipeline(), conn.cursor() as cur:
        cur.executemany(
            """
            insert into player_metrics (
              season_id, player_id, computed_for_gw, horizon,
              form_raw, form_score, fixture_raw, fixture_score, home_raw, home_score,
              xgi_raw, xgi_score, value_raw, value_score, minutes_raw, minutes_score,
              trend_raw, trend_score, fixture_count, availability
            ) values (
              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            on conflict (season_id, player_id, computed_for_gw, horizon) do update set
              form_raw = excluded.form_raw, form_score = excluded.form_score,
              fixture_raw = excluded.fixture_raw, fixture_score = excluded.fixture_score,
              home_raw = excluded.home_raw, home_score = excluded.home_score,
              xgi_raw = excluded.xgi_raw, xgi_score = excluded.xgi_score,
              value_raw = excluded.value_raw, value_score = excluded.value_score,
              minutes_raw = excluded.minutes_raw, minutes_score = excluded.minutes_score,
              trend_raw = excluded.trend_raw, trend_score = excluded.trend_score,
              fixture_count = excluded.fixture_count, availability = excluded.availability,
              computed_at = now()
            """,
            [
                (
                    season_id, row.player_id, row.computed_for_gw, row.horizon,
                    row.form_raw, row.form_score, row.fixture_raw, row.fixture_score,
                    row.home_raw, row.home_score, row.xgi_raw, row.xgi_score,
                    row.value_raw, row.value_score, row.minutes_raw, row.minutes_score,
                    row.trend_raw, row.trend_score, row.fixture_count, row.availability,
                )
                for row in rows
            ],
        )
    return int(version["id"])


def current_season_id(conn: Connection) -> str:
    row = conn.execute("select id from seasons where is_current = true limit 1").fetchone()
    if not row:
        raise RuntimeError("no current season — run ingest bootstrap first")
    return str(row["id"])


def get_entry_cache(conn: Connection, entry_id: int, event: int, ttl_seconds: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        select payload from entry_cache
         where entry_id = %s and event = %s
           and fetched_at > now() - (%s || ' seconds')::interval
        """,
        [entry_id, event, ttl_seconds],
    ).fetchone()
    return row["payload"] if row else None


def get_suggested_lineup(
    conn: Connection,
    user_id: Any,
    entry_id: int,
    gameweek: int,
    squad_hash: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        select lineup from suggested_lineups
         where user_id = %s and entry_id = %s and gameweek = %s and squad_hash = %s
        """,
        [user_id, entry_id, gameweek, squad_hash],
    ).fetchone()
    if row is None:
        return None
    lineup = row["lineup"]
    return lineup if isinstance(lineup, dict) else None


def save_suggested_lineup(
    conn: Connection,
    *,
    user_id: Any,
    entry_id: int,
    gameweek: int,
    squad_hash: str,
    lineup: dict[str, Any],
) -> None:
    conn.execute(
        """
        insert into suggested_lineups (user_id, entry_id, gameweek, squad_hash, lineup)
        values (%s, %s, %s, %s, %s)
        on conflict (user_id, entry_id, gameweek, squad_hash) do update
          set lineup = excluded.lineup,
              created_at = now()
        """,
        [user_id, entry_id, gameweek, squad_hash, Json(lineup)],
    )


def put_entry_cache(conn: Connection, entry_id: int, event: int, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        insert into entry_cache (entry_id, event, payload, fetched_at)
        values (%s, %s, %s, now())
        on conflict (entry_id, event) do update set payload = excluded.payload, fetched_at = now()
        """,
        [entry_id, event, Json(payload)],
    )


def save_snapshot(conn: Connection, snapshot: TeamSnapshot, user_id: UUID | None) -> dict[str, Any]:
    existing = conn.execute(
        """
        select * from team_snapshots
         where entry_id = %s and created_by is not distinct from %s and content_hash = %s
        """,
        [snapshot.entry_id, user_id, snapshot.content_hash],
    ).fetchone()
    if existing:
        return existing
    return conn.execute(
        """
        insert into team_snapshots (
          entry_id, event, season_id, picks, bank, team_value, free_transfers, selling_prices,
          chips_available, chips_used, active_chip, flags, overrides, created_by, content_hash
        ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        returning *
        """,
        [
            snapshot.entry_id, snapshot.event, snapshot.season_id, Json(snapshot.picks),
            snapshot.bank, snapshot.team_value, snapshot.free_transfers, Json(snapshot.selling_prices),
            Json(snapshot.chips_available), Json(snapshot.chips_used), snapshot.active_chip,
            Json(snapshot.flags), Json(snapshot.overrides), user_id, snapshot.content_hash,
        ],
    ).fetchone()


@dataclass(frozen=True)
class RetentionWindows:
    next_gw: int
    stats_min_round: int
    metrics_min_gw: int
    metrics_max_gw: int
    snapshot_days: int
    cache_seconds: int
    agent_keep_hours: int
    log_days: int


def retention_windows(next_gw: int) -> RetentionWindows:
    return RetentionWindows(
        next_gw=next_gw,
        stats_min_round=next_gw - MATCH_STATS_RETENTION_ROUNDS,
        metrics_min_gw=next_gw,
        metrics_max_gw=next_gw + METRIC_FORWARD_GWS - 1,
        snapshot_days=DAILY_SNAPSHOT_RETENTION_DAYS,
        cache_seconds=ENTRY_CACHE_PRUNE_SECONDS,
        agent_keep_hours=AGENT_RUN_KEEP_HOURS,
        log_days=LOG_RETENTION_DAYS,
    )


def _next_gw(conn: Connection) -> int | None:
    row = conn.execute("select id from gameweeks where is_next = true limit 1").fetchone()
    if row:
        return int(row["id"])
    row = conn.execute("select id from gameweeks order by id desc limit 1").fetchone()
    return int(row["id"]) if row else None


def _delete(conn: Connection, sql: str, params: list[Any] | None = None) -> int:
    result = conn.execute(sql, params)
    return int(result.rowcount or 0)


def prune_retention(conn: Connection) -> dict[str, int]:
    nxt = _next_gw(conn)
    windows = retention_windows(nxt) if nxt is not None else None
    counts: dict[str, int] = {}
    if windows is not None:
        counts["player_gameweek_stats"] = _delete(
            conn,
            "delete from player_gameweek_stats where round < %s",
            [windows.stats_min_round],
        )
        counts["player_metrics"] = _delete(
            conn,
            """
            delete from player_metrics
             where computed_for_gw < %s or computed_for_gw > %s
            """,
            [windows.metrics_min_gw, windows.metrics_max_gw],
        )
        counts["suggested_lineups"] = _delete(
            conn,
            "delete from suggested_lineups where gameweek < %s",
            [windows.next_gw],
        )
    counts["player_daily_snapshots"] = _delete(
        conn,
        "delete from player_daily_snapshots where snapshot_date < current_date - %s",
        [DAILY_SNAPSHOT_RETENTION_DAYS],
    )
    counts["entry_cache"] = _delete(
        conn,
        """
        delete from entry_cache
         where fetched_at < now() - (%s || ' seconds')::interval
        """,
        [ENTRY_CACHE_PRUNE_SECONDS],
    )
    counts["agent_runs"] = _delete(
        conn,
        """
        delete from agent_runs
         where status not in ('queued', 'running')
           and id not in (
                select id from (
                  select distinct on (user_id, entry_id) id
                    from agent_runs
                   where status = 'succeeded'
                   order by user_id, entry_id, finished_at desc nulls last
                ) latest
           )
           and coalesce(finished_at, created_at) < now() - (%s || ' hours')::interval
        """,
        [AGENT_RUN_KEEP_HOURS],
    )
    counts["team_snapshots"] = _delete(
        conn,
        """
        delete from team_snapshots ts
         where not exists (select 1 from agent_runs ar where ar.snapshot_id = ts.id)
           and ts.id not in (
                select id from (
                  select distinct on (created_by, entry_id) id
                    from team_snapshots
                   order by created_by, entry_id, fetched_at desc
                ) latest
           )
        """,
    )
    counts["data_versions"] = _delete(
        conn,
        """
        delete from data_versions
         where created_at < now() - (%s || ' days')::interval
           and id not in (
                select data_version from agent_runs where data_version is not null
           )
        """,
        [LOG_RETENTION_DAYS],
    )
    counts["ingest_runs"] = _delete(
        conn,
        """
        delete from ingest_runs
         where started_at < now() - (%s || ' days')::interval
           and id not in (
                select ingest_run_id from data_versions where ingest_run_id is not null
           )
        """,
        [LOG_RETENTION_DAYS],
    )
    return counts
