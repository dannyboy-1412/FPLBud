from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import HTTPException
from psycopg import Connection

from fplcore.agent.runner import try_llm_cap
from fplcore.client import FplClient, FplNotFoundError
from fplcore.constants import (
    DEFAULT_WEIGHTS,
    ENTRY_CACHE_TTL_SECONDS,
    METRIC_DESCRIPTIONS,
    METRIC_LABELS,
    PRICE_PRESSURE_CAVEAT,
)
from fplcore.db import stats_repo
from fplcore.db.repos import (
    current_season_id,
    get_entry_cache,
    get_suggested_lineup,
    put_entry_cache,
    save_suggested_lineup,
)
from fplcore.explain.template import TemplateExplainer
from fplcore.lineup import (
    LineupRejected,
    build_lineup_dossier,
    choose_lineup,
    lineup_cache_hash,
    validate_lineup,
)
from fplcore.metrics.combine import (
    availability,
    combined_score,
    projected_points,
    renormalise_weights,
)
from fplcore.models import BootstrapStatic, Entry, EntryHistory, PicksPayload, TransferRow
from fplcore.optimise import PlayerOpt, optimise_horizon
from fplcore.settings import Settings
from fplcore.stats.insights import (
    bonus_leaders,
    defensive_leaders,
    differentials,
    finishing_variance,
    in_form,
    set_piece_takers,
)
from fplcore.stats.market import movers_24h, price_movers, price_pressure, top_transfers
from fplcore.stats.report import (
    overperforming_players,
    projection_for_row,
    squad_score_for_xi,
    underperforming_players,
    xi_element_ids,
    xi_projections,
)
from fplcore.stats.season import captain_returns, season_rows, season_summary
from fplcore.stats.squad import (
    captaincy_board,
    ownership_profile,
    squad_differentials,
    template_threats,
)
from fplcore.team_import import TeamSnapshot, build_snapshot, merged_from_payloads


async def load_merged_entry(conn: Connection, client: FplClient, entry_id: int) -> tuple[dict[str, Any], Any]:
    bootstrap = await client.bootstrap_static()
    entry = await client.entry(entry_id)
    cached = get_entry_cache(conn, entry_id, entry.current_event, ENTRY_CACHE_TTL_SECONDS)
    if cached:
        return cached, bootstrap
    picks = await client.entry_picks(entry_id, entry.current_event)
    history = await client.entry_history(entry_id)
    transfers = await client.entry_transfers(entry_id)
    payload = {
        "entry": entry.model_dump(mode="json"),
        "picks": picks.model_dump(mode="json"),
        "history": history.model_dump(mode="json"),
        "transfers": [t.model_dump(mode="json") for t in transfers],
    }
    put_entry_cache(conn, entry_id, entry.current_event, payload)
    conn.commit()
    return payload, bootstrap


def snapshot_from_cache(
    payload: dict[str, Any],
    bootstrap: BootstrapStatic,
    season_id: str,
    overrides: dict[str, Any] | None = None,
) -> TeamSnapshot:
    players = {el.id: el for el in bootstrap.elements}
    merged = merged_from_payloads(
        Entry.model_validate(payload["entry"]),
        PicksPayload.model_validate(payload["picks"]),
        EntryHistory.model_validate(payload["history"]),
        [TransferRow.model_validate(t) for t in payload.get("transfers") or []],
    )
    return build_snapshot(
        merged=merged,
        players=players,
        chip_windows=bootstrap.chips,
        season_id=season_id,
        max_extra_free_transfers=bootstrap.game_settings.max_extra_free_transfers,
        overrides=overrides,
    )


def public_team_view(snapshot: TeamSnapshot, *, squad_score: float = 0.0) -> dict[str, Any]:
    return {
        "entry_id": snapshot.entry_id,
        "name": snapshot.name,
        "manager": snapshot.manager,
        "overall_rank": snapshot.overall_rank,
        "event": snapshot.event,
        "picks": snapshot.picks,
        "squad_players": snapshot.squad_players,
        "bank": snapshot.bank,
        "team_value": snapshot.team_value,
        "free_transfers": snapshot.free_transfers,
        "selling_prices": snapshot.selling_prices,
        "chips_available": snapshot.chips_available,
        "chips_used": snapshot.chips_used,
        "active_chip": snapshot.active_chip,
        "flags": snapshot.flags,
        "estimated": True,
        "caveat": "Transfers already made for the next gameweek are hidden until the deadline.",
        "squad_score": squad_score,
    }


def _xi_metric_rows(conn: Connection, snapshot: TeamSnapshot) -> tuple[list[int], dict[int, dict[str, Any]]]:
    xi_ids = xi_element_ids(snapshot.squad_players)
    rows = stats_repo.next_gw_metric_rows(conn)
    return xi_ids, {int(row["id"]): row for row in rows}


def compute_squad_score(conn: Connection, snapshot: TeamSnapshot) -> float:
    xi_ids, rows_by_id = _xi_metric_rows(conn, snapshot)
    return _squad_score(xi_ids, rows_by_id)


def _squad_score(xi_ids: list[int], rows_by_id: dict[int, dict[str, Any]]) -> float:
    projections = xi_projections(xi_ids, rows_by_id, DEFAULT_WEIGHTS)
    field = [projection_for_row(row, DEFAULT_WEIGHTS) for row in rows_by_id.values()]
    return squad_score_for_xi(projections, field)


def team_short_names(conn: Connection) -> dict[int, str]:
    season = current_season_id(conn)
    rows = conn.execute("select id, short_name from teams where season_id = %s", [season])
    return {int(row["id"]): str(row["short_name"]) for row in rows}


def with_pitch_details(
    players: list[dict[str, Any]],
    team_names: dict[int, str],
    fixtures_by_team: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    detailed: list[dict[str, Any]] = []
    for player in players:
        team_id = int(player["team_id"])
        detailed.append(
            {
                **player,
                "team_short": team_names.get(team_id, ""),
                "fixtures": fixtures_by_team.get(team_id, []),
            }
        )
    return detailed


def public_team_payload(
    conn: Connection,
    snapshot: TeamSnapshot,
    *,
    team_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    view = public_team_view(snapshot, squad_score=compute_squad_score(conn, snapshot))
    names = team_names if team_names is not None else team_short_names(conn)
    view["squad_players"] = with_pitch_details(view["squad_players"], names, stats_repo.next_event_fixtures(conn))
    squad_ids = {int(player["element"]) for player in snapshot.squad_players}
    rows = stats_repo.current_player_rows(conn)
    view["underperforming"] = underperforming_players(rows, squad_ids)
    view["overperforming"] = overperforming_players(rows, squad_ids)
    return view


def build_horizon_plan(
    conn: Connection,
    snapshot: TeamSnapshot,
    *,
    weights: dict[str, float],
    horizon: int,
    max_hits: int | None = None,
    lock_ids: list[int] | None = None,
    exclude_ids: list[int] | None = None,
) -> dict[str, Any] | None:
    players = load_opt_players(conn, snapshot, weights, horizon)
    if not players:
        return None
    unlimited = (snapshot.active_chip or "") in {"wildcard", "freehit"}
    solved = optimise_horizon(
        players,
        bank=snapshot.bank,
        free_transfers=snapshot.free_transfers,
        horizon=horizon,
        max_hits=max_hits,
        lock_ids=lock_ids or [],
        exclude_ids=exclude_ids or [],
        unlimited_transfers=unlimited,
    )
    plan = suggestion_from_opt(solved, snapshot)
    plan["explanation"] = TemplateExplainer().explain(plan)
    plan["explanation_source"] = "template"
    return plan


def meta_payload(conn: Connection) -> dict[str, Any]:
    season = conn.execute("select id from seasons where is_current = true").fetchone()
    season_id = str(season["id"]) if season else None
    current = stats_repo.started_gameweek(conn, season_id) if season_id else None
    nxt = stats_repo.upcoming_gameweek(conn, season_id) if season_id else None
    version = conn.execute("select id from data_versions order by id desc limit 1").fetchone()
    settings_row = conn.execute(
        "select squad_select, squad_min_play, squad_max_play, short_name from positions order by id"
    ).fetchall()
    ingest = conn.execute(
        "select job, finished_at, ok from ingest_runs where ok = true order by finished_at desc limit 1"
    ).fetchone()
    return {
        "season_id": season["id"] if season else None,
        "current_event": current,
        "next_event": nxt,
        "data_version": version["id"] if version else None,
        "default_weights": DEFAULT_WEIGHTS,
        "metric_labels": METRIC_LABELS,
        "metric_descriptions": METRIC_DESCRIPTIONS,
        "positions": [dict(r) for r in settings_row],
        "last_ingest": dict(ingest) if ingest else None,
    }


def ranked_players(
    conn: Connection,
    *,
    weights: dict[str, float],
    position: int | None = None,
    team: int | None = None,
    max_cost: int | None = None,
    horizon: int = 1,
) -> list[dict[str, Any]]:
    season = current_season_id(conn)
    next_gw = stats_repo.next_gw_id(conn, season)
    w = renormalise_weights(weights)
    sql = """
        select p.*, t.short_name as team_short, m.form_score, m.fixture_score, m.home_score, m.xgi_score,
               m.value_score, m.minutes_score, m.trend_score, m.fixture_count, m.availability,
               m.computed_for_gw
          from players p
          join teams t on t.season_id = p.season_id and t.id = p.team_id
          join player_metrics m on m.season_id = p.season_id and m.player_id = p.id and m.horizon = 1
         where p.season_id = %s and m.computed_for_gw between %s and %s
    """
    params: list[Any] = [season, next_gw, next_gw + horizon - 1]
    if position:
        sql += " and p.position_id = %s"
        params.append(position)
    if team:
        sql += " and p.team_id = %s"
        params.append(team)
    if max_cost:
        sql += " and p.now_cost <= %s"
        params.append(max_cost)
    rows = list(conn.execute(sql, params))
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        rec = grouped.setdefault(
            int(row["id"]),
            {
                "id": int(row["id"]),
                "web_name": row["web_name"],
                "team_id": int(row["team_id"]),
                "team_short": row["team_short"],
                "position_id": int(row["position_id"]),
                "now_cost": int(row["now_cost"]),
                "selected_by_percent": float(row["selected_by_percent"]),
                "status": row["status"],
                "news": row["news"],
                "chance_of_playing_next_round": row["chance_of_playing_next_round"],
                "scores": {},
                "proj": 0.0,
            },
        )
        gw = int(row["computed_for_gw"])
        scores = {
            "form": float(row["form_score"] or 0),
            "fixture": float(row["fixture_score"] or 0),
            "home": float(row["home_score"] or 0),
            "xgi": float(row["xgi_score"] or 0),
            "value": float(row["value_score"] or 0),
            "minutes": float(row["minutes_score"] or 0),
            "trend": float(row["trend_score"] or 0),
        }
        if gw == next_gw:
            rec["scores"] = scores
        k = gw - next_gw + 1
        rec["proj"] += projected_points(
            score=combined_score(scores, w),
            fixture_count=int(row["fixture_count"]),
            avail=float(row["availability"] if k == 1 else availability(
                chance_of_playing_next_round=row["chance_of_playing_next_round"],
                status=row["status"],
                k=k,
            )),
        )
    ranked = sorted(grouped.values(), key=lambda r: r["proj"], reverse=True)
    for i, rec in enumerate(ranked, start=1):
        rec["rank"] = i
        rec["proj"] = round(rec["proj"], 2)
        rec["effective_weights"] = w
    return ranked


def player_detail(conn: Connection, player_id: int) -> dict[str, Any] | None:
    season = current_season_id(conn)
    player = conn.execute(
        """
        select p.*, t.short_name as team_short, t.name as team_name
          from players p join teams t on t.season_id = p.season_id and t.id = p.team_id
         where p.season_id = %s and p.id = %s
        """,
        [season, player_id],
    ).fetchone()
    if player is None:
        return None
    metrics = list(
        conn.execute(
            """
            select * from player_metrics
             where season_id = %s and player_id = %s and horizon = 1
             order by computed_for_gw
            """,
            [season, player_id],
        )
    )
    history = list(
        conn.execute(
            """
            select round, minutes, total_points, expected_goals, expected_assists, was_home, opponent_team
              from player_gameweek_stats
             where season_id = %s and player_id = %s
             order by round desc limit 8
            """,
            [season, player_id],
        )
    )
    return {"player": dict(player), "metrics": [dict(m) for m in metrics], "history": [dict(h) for h in history]}


def load_opt_players(conn: Connection, snapshot: TeamSnapshot, weights: dict[str, float], horizon: int) -> list[PlayerOpt]:
    season = snapshot.season_id
    next_gw = stats_repo.next_gw_id(conn, season)
    current = {int(p["element"]) for p in snapshot.picks}
    selling = {int(k): int(v) for k, v in snapshot.selling_prices.items()}
    rows = list(
        conn.execute(
            """
            select p.id, p.web_name, p.team_id, p.position_id, p.now_cost, p.status,
                   p.chance_of_playing_next_round, p.can_transact, p.removed,
                   m.computed_for_gw, m.form_score, m.fixture_score, m.home_score, m.xgi_score,
                   m.value_score, m.minutes_score, m.trend_score, m.fixture_count
              from players p
              join player_metrics m on m.season_id = p.season_id and m.player_id = p.id and m.horizon = 1
             where p.season_id = %s and m.computed_for_gw between %s and %s
            """,
            [season, next_gw, next_gw + max(horizon, 1) - 1],
        )
    )
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        rec = by_id.setdefault(
            int(row["id"]),
            {
                "id": int(row["id"]),
                "web_name": row["web_name"],
                "team_id": int(row["team_id"]),
                "position_id": int(row["position_id"]),
                "cost": int(row["now_cost"]),
                "sell": selling.get(int(row["id"]), int(row["now_cost"])),
                "in_squad": int(row["id"]) in current,
                "can_in": bool(row["can_transact"]) and not row["removed"] and row["status"] != "u",
                "proj": {},
                "scores_gw1": {},
                "status": row["status"],
                "cop": row["chance_of_playing_next_round"],
            },
        )
        scores = {
            "form": float(row["form_score"] or 0),
            "fixture": float(row["fixture_score"] or 0),
            "home": float(row["home_score"] or 0),
            "xgi": float(row["xgi_score"] or 0),
            "value": float(row["value_score"] or 0),
            "minutes": float(row["minutes_score"] or 0),
            "trend": float(row["trend_score"] or 0),
        }
        gw = int(row["computed_for_gw"])
        k = gw - next_gw + 1
        rec["proj"][gw] = projected_points(
            score=combined_score(scores, weights),
            fixture_count=int(row["fixture_count"]),
            avail=availability(chance_of_playing_next_round=row["chance_of_playing_next_round"], status=row["status"], k=max(k, 1)),
        )
        if gw == next_gw:
            rec["scores_gw1"] = scores
    out: list[PlayerOpt] = []
    for rec in by_id.values():
        proj = [float(rec["proj"].get(next_gw + i, 0.0)) for i in range(max(horizon, 1))]
        out.append(
            PlayerOpt(
                id=rec["id"],
                web_name=rec["web_name"],
                team_id=rec["team_id"],
                position_id=rec["position_id"],
                cost=rec["cost"],
                sell=rec["sell"],
                in_squad=rec["in_squad"],
                can_in=rec["can_in"],
                locked=False,
                proj=proj,
                scores_gw1=rec["scores_gw1"],
            )
        )
    return out


def suggestion_from_opt(solved: dict[str, Any], snapshot: TeamSnapshot) -> dict[str, Any]:
    best = solved["best"]
    roll = solved["roll"]
    transfers = [
        {
            "out": m.out_id,
            "in": m.in_id,
            "out_name": m.out_name,
            "in_name": m.in_name,
            "cost_delta": m.cost_delta,
            "metric_deltas": m.metric_deltas,
        }
        for m in best.moves
    ]
    return {
        "horizon": solved["settings"].n,
        "transfers": transfers,
        "hits": best.hits,
        "gain_vs_roll": round(best.objective - (roll.objective if roll else 0), 2),
        "roll_alternative": {
            "hits": roll.hits,
            "gain_vs_roll": 0,
            "transfers": [],
        } if roll else None,
        "xi": [{"id": pid} for pid in best.xi_ids],
        "bench": [{"id": pid} for pid in best.bench_ids],
        "captain": {"id": best.captain_id},
        "vice": {"id": best.vice_id},
        "chips": [],
        "flags": snapshot.flags,
        "reason_codes": ["ROLL_PREFERRED"] if not transfers else ["CAPTAIN_MARGIN"],
        "projected_points_by_gw": best.projected_points_by_gw,
        "bank_after": best.bank_after,
        "headline": "Roll the transfer" if not transfers else ", ".join(
            f"Sell {t['out_name']}, buy {t['in_name']}" for t in transfers
        ),
        "explanation": None,
        "explanation_source": "template",
    }


def market_payload(conn: Connection) -> dict[str, Any]:
    players = stats_repo.current_player_rows(conn)
    _today, yesterday = stats_repo.snapshot_transfer_rows(conn)
    for player in players:
        prev = yesterday.get(int(player["id"]))
        if prev:
            player["daily_change"] = int(player["now_cost"]) - int(prev["now_cost"])
    transfers = top_transfers(players)
    movers = price_movers(players)
    managers = stats_repo.total_players(conn)
    pressure = price_pressure(players, managers) if managers else {"likely_to_rise": [], "likely_to_fall": []}
    return {
        **transfers,
        **movers,
        "movers_24h": movers_24h(players, yesterday),
        **pressure,
        "total_players": managers,
        "caveat": PRICE_PRESSURE_CAVEAT,
    }


def insights_payload(
    conn: Connection, *, weights: dict[str, float], position: int | None = None
) -> dict[str, Any]:
    players = stats_repo.current_player_rows(conn, position=position)
    recent = stats_repo.recent_aggregates(conn, position=position)
    ranked = ranked_players(conn, weights=weights, position=position, horizon=3)
    variance = finishing_variance(players)
    return {
        "in_form": in_form(recent),
        "underperformers": variance["underperformers"],
        "overperformers": variance["overperformers"],
        "differentials": differentials(ranked),
        "defensive": defensive_leaders(recent),
        "bonus": bonus_leaders(players),
        "set_pieces": set_piece_takers(players) if position is None else [],
    }


def squad_stats_payload(conn: Connection, snapshot: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    picks = list(snapshot.get("picks") or [])
    squad_ids = {int(p["element"]) for p in picks}
    starter_ids = {int(p["element"]) for p in picks if int(p.get("position") or 0) <= 11}
    ranked_h1 = {int(r["id"]): r for r in ranked_players(conn, weights=weights, horizon=1)}
    ranked_h3 = ranked_players(conn, weights=weights, horizon=3)
    players = {int(p["id"]): p for p in stats_repo.current_player_rows(conn)}
    fixtures = stats_repo.next_event_fixtures(conn)
    starters: list[dict[str, Any]] = []
    squad_rows: list[dict[str, Any]] = []
    for pick in picks:
        pid = int(pick["element"])
        player = players.get(pid)
        ranked = ranked_h1.get(pid)
        if player is None:
            continue
        rec = {
            "id": pid,
            "web_name": player["web_name"],
            "team_short": player["team_short"],
            "team_id": int(player["team_id"]),
            "position_id": int(player["position_id"]),
            "now_cost": int(player["now_cost"]),
            "selected_by_percent": float(player["selected_by_percent"]),
            "status": player["status"],
            "chance_of_playing_next_round": player["chance_of_playing_next_round"],
            "proj": float(ranked["proj"]) if ranked else 0.0,
            "is_captain": bool(pick.get("is_captain")),
            "is_vice_captain": bool(pick.get("is_vice_captain")),
            "fixtures": fixtures.get(int(player["team_id"]), []),
        }
        squad_rows.append(rec)
        if pid in starter_ids:
            starters.append(rec)
    crowd = stats_repo.latest_crowd_captain(conn)
    crowd_view = None
    if crowd:
        crowd_view = {
            "event": int(crowd["event"]),
            "id": int(crowd["most_captained"]),
            "web_name": crowd["web_name"],
            "team_short": crowd["team_short"],
            "event_points": int(crowd["event_points"] or 0),
        }
    return {
        "captaincy": captaincy_board(starters, crowd_view),
        "template_threats": template_threats(ranked_h3, squad_ids),
        "differentials": squad_differentials(ranked_h3, squad_ids),
        "ownership": ownership_profile(squad_rows, starter_ids),
    }


def season_stats_payload(
    history: EntryHistory,
    gameweeks: list[dict[str, Any]],
    picks_by_event: dict[int, dict[str, Any]],
    points: dict[tuple[int, int], int],
    names: dict[int, str],
) -> dict[str, Any]:
    gw_map = {int(g["id"]): g for g in gameweeks}
    most_captained = {int(g["id"]): (int(g["most_captained"]) if g.get("most_captained") else None) for g in gameweeks}
    rows = season_rows(history.current, gw_map, history.chips)
    returns = captain_returns(history.current, picks_by_event, points, names, most_captained)
    return {"rows": rows, "summary": season_summary(rows), "captain_returns": returns}


def _squad_opts(conn: Connection, snapshot: TeamSnapshot, weights: dict[str, float]) -> list[PlayerOpt]:
    loaded = {player.id: player for player in load_opt_players(conn, snapshot, weights, horizon=1)}
    opts: list[PlayerOpt] = []
    for player in snapshot.squad_players:
        element = int(player["element"])
        existing = loaded.get(element)
        if existing is not None:
            opts.append(replace(existing, in_squad=True, can_in=False, locked=True))
            continue
        opts.append(
            PlayerOpt(
                id=element,
                web_name=str(player.get("web_name") or ""),
                team_id=int(player["team_id"]),
                position_id=int(player["position_id"]),
                cost=int(player.get("now_cost") or 0),
                sell=int(player.get("now_cost") or 0),
                in_squad=True,
                can_in=False,
                locked=True,
                proj=[0.0],
                scores_gw1={},
            )
        )
    return opts


def _cached_lineup(payload: dict[str, Any] | None, positions: dict[int, int]) -> dict[str, Any] | None:
    if not payload:
        return None
    try:
        validate_lineup(payload, positions, source=str(payload.get("source") or "llm"))
    except LineupRejected:
        return None
    return payload


async def build_suggested_xi(conn: Connection, settings: Settings, user_id: Any) -> dict[str, Any]:
    """Line up the signed-in squad for the next gameweek.

    A stored row for this user, team, gameweek and squad is returned as-is and
    does not reserve a model call. News and metric rebuilds leave that row in place.
    """
    profile = conn.execute(
        "select fpl_entry_id, weights from public.profiles where id = %s",
        [user_id],
    ).fetchone()
    if not profile or not profile["fpl_entry_id"]:
        raise HTTPException(status_code=400, detail="no team saved")
    entry_id = int(profile["fpl_entry_id"])
    weights = profile["weights"] or DEFAULT_WEIGHTS
    try:
        async with FplClient(settings) as client:
            payload, bootstrap = await load_merged_entry(conn, client, entry_id)
    except FplNotFoundError:
        raise HTTPException(status_code=404, detail="team not found") from None
    snapshot = snapshot_from_cache(payload, bootstrap, current_season_id(conn))
    opts = _squad_opts(conn, snapshot, weights)
    if len(opts) != 15:
        raise HTTPException(status_code=422, detail="squad is incomplete")
    player_ids = [int(player["element"]) for player in snapshot.squad_players]
    squad_hash = lineup_cache_hash(player_ids, weights)
    gameweek = stats_repo.next_gw_id(conn, snapshot.season_id)
    positions = {player.id: player.position_id for player in opts}
    cached = _cached_lineup(
        get_suggested_lineup(conn, user_id, entry_id, gameweek, squad_hash),
        positions,
    )
    if cached is not None:
        return cached

    team_names = {team.id: team.short_name for team in bootstrap.teams}
    projections = {player.id: float(player.proj[0]) if player.proj else 0.0 for player in opts}
    dossier = build_lineup_dossier(
        snapshot.squad_players,
        projections,
        team_names,
        stats_repo.next_event_fixtures(conn),
    )
    allow_llm = bool(settings.llm_api_key and settings.llm_model)
    if allow_llm:
        allow_llm = try_llm_cap(conn, settings.llm_daily_call_cap)
        if allow_llm:
            conn.commit()
    try:
        lineup = await choose_lineup(opts, dossier, settings=settings, allow_llm=allow_llm)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="could not build a lineup") from exc
    stored = lineup.to_dict()
    save_suggested_lineup(
        conn,
        user_id=user_id,
        entry_id=entry_id,
        gameweek=gameweek,
        squad_hash=squad_hash,
        lineup=stored,
    )
    conn.commit()
    return stored
