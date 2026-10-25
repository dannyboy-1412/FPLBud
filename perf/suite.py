"""Backend performance suite.

Run with ``uv run python -m perf`` or ``uv run pytest perf``.
Writes ``perf/report.html``.
"""

from __future__ import annotations

import asyncio
import json
import platform
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from starlette.requests import Request

from api.limiter import limiter_key
from api.services import public_team_view, suggestion_from_opt, with_pitch_details
from api.weights_query import parse_weights_query
from fplcore.agent.chips import advise_chips
from fplcore.agent.queue import _weights_hash
from fplcore.client import TokenBucket
from fplcore.constants import ALL_METRICS, DEFAULT_WEIGHTS, PREFILTER_PER_POSITION
from fplcore.db.repos import retention_windows, round_points_from_history, season_id_from_bootstrap
from fplcore.explain.factory import get_explainer
from fplcore.explain.protocol import HorizonResult
from fplcore.explain.template import TemplateExplainer
from fplcore.gameweeks import pick_started_gameweek, pick_upcoming_gameweek
from fplcore.lineup import build_lineup_dossier, lineup_cache_hash, validate_lineup
from fplcore.llm import _parse_json_content, grounding_ok
from fplcore.metrics.combine import (
    availability,
    combined_score,
    playing_share,
    poisson_clean_sheet,
    projected_points,
)
from fplcore.metrics.compute import (
    compute_form_raw,
    compute_minutes_raw,
    compute_player_metrics,
    compute_trend_raw,
    compute_xgi_raw,
    fixture_features_for_gw,
)
from fplcore.models import (
    BootstrapStatic,
    ElementSummary,
    Entry,
    EntryHistory,
    Fixture,
    PicksPayload,
    TransferRow,
)
from fplcore.optimise import (
    HORIZON_SETTINGS,
    SolvedPlan,
    TransferMove,
    _prefilter,
    optimise_horizon,
    pick_best_plan,
    solve_for_transfers,
)
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
    performing_players,
    projection_for_row,
    squad_score_for_xi,
    underperforming_players,
    xi_expected_points,
    xi_projections,
)
from fplcore.stats.season import captain_returns, season_rows, season_summary
from fplcore.stats.squad import (
    captaincy_board,
    ownership_profile,
    squad_differentials,
    template_threats,
)
from fplcore.team_import import (
    build_snapshot,
    derive_free_transfers,
    estimate_selling_price,
    merged_from_payloads,
)
from perf.harness import Job, ProfileEntry, Report, Result, format_seconds, measure, profile
from perf.report import write_report
from perf.workloads import World, load

REPORT_PATH = Path(__file__).resolve().parent / "report.html"

REQUIRED_MODULES = (
    "fplcore.models",
    "fplcore.metrics.compute",
    "fplcore.metrics.combine",
    "fplcore.optimise",
    "fplcore.team_import",
    "fplcore.stats.market",
    "fplcore.stats.insights",
    "fplcore.stats.squad",
    "fplcore.stats.season",
    "fplcore.stats.report",
    "fplcore.explain",
    "fplcore.lineup",
    "fplcore.gameweeks",
    "fplcore.agent.chips",
    "fplcore.agent.queue",
    "fplcore.llm",
    "api.services",
    "api.weights_query",
    "api.limiter",
    "fplcore.db.repos",
    "fplcore.client",
    "fplcore.settings",
)


def run() -> Report:
    """Time and profile the backend, then write ``perf/report.html``."""
    started = time.perf_counter()
    world = load()
    load_s = time.perf_counter() - started
    cleanups: list[Callable[[], None]] = []
    results: list[Result] = []
    try:
        for job in build_jobs(world, cleanups):
            print(f"timing {job.module}.{job.name}", flush=True)
            timing = measure(job.call, loops=job.loops, repeats=job.repeats)
            self_rows: tuple[ProfileEntry, ...] = ()
            cumulative_rows: tuple[ProfileEntry, ...] = ()
            total = 0.0
            if job.profile:
                print(f"profiling {job.module}.{job.name}", flush=True)
                self_rows, cumulative_rows, total = profile(job.call)
            results.append(
                Result(
                    name=job.name,
                    module=job.module,
                    workload=job.workload,
                    suspect=job.suspect,
                    timing=timing,
                    profiled=job.profile,
                    profile_self=self_rows,
                    profile_cumulative=cumulative_rows,
                    profile_total_s=total,
                )
            )
            print(
                f"  mean {format_seconds(timing.mean_s)}, best {format_seconds(timing.best_s)}",
                flush=True,
            )
    finally:
        for cleanup in cleanups:
            cleanup()
    if not results:
        raise RuntimeError("performance suite produced no results")
    report = Report(
        path=REPORT_PATH,
        results=tuple(results),
        dataset=world.dataset,
        load_s=load_s,
        elapsed_s=time.perf_counter() - started,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        python_version=platform.python_version(),
        platform_name=platform.platform(),
    )
    write_report(report)
    print(f"wrote {report.path}", flush=True)
    return report


def build_jobs(world: World, cleanups: list[Callable[[], None]]) -> list[Job]:
    jobs: list[Job] = []
    jobs.extend(_model_jobs(world))
    jobs.extend(_metric_jobs(world))
    jobs.extend(_optimise_jobs(world))
    jobs.extend(_team_jobs(world))
    jobs.extend(_stats_jobs(world))
    jobs.extend(_explain_jobs())
    jobs.extend(_lineup_jobs(world))
    jobs.extend(_gameweek_jobs(world))
    jobs.extend(_chip_jobs(world))
    jobs.extend(_llm_jobs())
    jobs.extend(_api_jobs(world))
    jobs.extend(_db_jobs(world))
    jobs.extend(_client_jobs(cleanups))
    jobs.extend(_settings_jobs())
    return jobs


def _job(
    name: str,
    module: str,
    workload: str,
    call: Callable[[], object],
    *,
    loops: int | None = None,
    repeats: int = 5,
    profile: bool = False,
    suspect: str = "",
) -> Job:
    return Job(
        name=name,
        module=module,
        workload=workload,
        call=call,
        repeats=repeats,
        loops=loops,
        profile=profile,
        suspect=suspect,
    )


def _heavy(
    name: str,
    module: str,
    workload: str,
    call: Callable[[], object],
    suspect: str,
    *,
    repeats: int = 3,
) -> Job:
    return _job(
        name,
        module,
        workload,
        call,
        loops=1,
        repeats=repeats,
        profile=True,
        suspect=suspect,
    )


def _model_jobs(world: World) -> list[Job]:
    def parse_bootstrap() -> object:
        parsed = BootstrapStatic.model_validate(json.loads(world.bootstrap_text))
        if not parsed.elements:
            raise RuntimeError("bootstrap parse produced no players")
        return parsed

    def parse_fixtures() -> object:
        parsed = [Fixture.model_validate(row) for row in json.loads(world.fixtures_text)]
        if not parsed:
            raise RuntimeError("fixture parse produced no rows")
        return parsed

    def parse_entry_payloads() -> object:
        entry = Entry.model_validate(json.loads(world.entry_text))
        picks = PicksPayload.model_validate(json.loads(world.picks_text))
        history = EntryHistory.model_validate(json.loads(world.history_text))
        transfers = [TransferRow.model_validate(row) for row in json.loads(world.transfers_text)]
        summary = ElementSummary.model_validate(json.loads(world.summary_text))
        if not picks.picks:
            raise RuntimeError("entry payloads did not parse")
        return entry, picks, history, transfers, summary

    return [
        _heavy(
            "parse_bootstrap",
            "fplcore.models",
            "bootstrap-static JSON, validated the way the FPL client does",
            parse_bootstrap,
            "Largest payload the client validates on each ingest.",
        ),
        _job(
            "parse_fixtures",
            "fplcore.models",
            f"{len(world.fixtures)} fixtures, JSON plus one model each",
            parse_fixtures,
        ),
        _job(
            "parse_entry_payloads",
            "fplcore.models",
            "entry, picks, history, transfers and one element summary",
            parse_entry_payloads,
        ),
    ]


def _metric_jobs(world: World) -> list[Job]:
    players = world.players
    history = world.history
    workload = (
        f"{len(players)} players, {len(history)} history rows, "
        f"{len(world.fixtures_frame)} fixtures, {len(world.snapshots)} snapshots, "
        f"gameweeks {world.next_gw}-{world.next_gw + 5}"
    )

    def compute_all() -> object:
        rows = compute_player_metrics(
            players=players,
            history=history,
            fixtures=world.fixtures_frame,
            snapshots=world.snapshots,
            next_gw=world.next_gw,
            last_rounds=world.last_rounds,
            total_players=world.manager_count,
            hours_since_deadline=world.hours_since_deadline,
        )
        expected = len(players) * 6
        if len(rows) != expected:
            raise RuntimeError(f"expected {expected} metric rows, got {len(rows)}")
        return rows

    def form() -> object:
        series = compute_form_raw(players, history, world.last_rounds)
        if len(series) != len(players):
            raise RuntimeError("form series does not match the player frame")
        return series

    def xgi() -> object:
        series = compute_xgi_raw(players, history, world.last_rounds)
        if len(series) != len(players):
            raise RuntimeError("xgi series does not match the player frame")
        return series

    def minutes() -> object:
        series = compute_minutes_raw(players, history)
        if len(series) != len(players):
            raise RuntimeError("minutes series does not match the player frame")
        return series

    def trend() -> object:
        series = compute_trend_raw(
            players,
            world.snapshots,
            total_players=world.manager_count,
            hours_since_deadline=world.hours_since_deadline,
        )
        if len(series) != len(players):
            raise RuntimeError("trend series does not match the player frame")
        return series

    def fixtures() -> object:
        last = None
        for offset in range(6):
            last = fixture_features_for_gw(players, world.fixtures_frame, world.next_gw + offset)
        return last

    def project() -> float:
        total = 0.0
        for card in world.cards:
            scores = {key: float(card[f"{key}_score"]) for key in ALL_METRICS}
            chance = card["chance_of_playing_next_round"]
            total += projected_points(
                score=combined_score(scores, DEFAULT_WEIGHTS),
                fixture_count=int(card["fixture_count"]),
                avail=availability(
                    chance_of_playing_next_round=None if chance is None else int(chance),
                    status=str(card["status"]),
                    k=1,
                ),
                minutes=playing_share(float(card["minutes_score"]), card.get("minutes")),
            )
            total += poisson_clean_sheet(1.1)
        return total

    return [
        _heavy(
            "compute_player_metrics",
            "fplcore.metrics.compute",
            workload,
            compute_all,
            "Ingest recomputes this for every player and the next six gameweeks.",
        ),
        _job(
            "compute_form_raw",
            "fplcore.metrics.compute",
            workload,
            form,
            suspect="Python loop over recent appearances. Suspected hot spot inside metric compute.",
        ),
        _job("compute_xgi_raw", "fplcore.metrics.compute", workload, xgi),
        _job("compute_minutes_raw", "fplcore.metrics.compute", workload, minutes),
        _job("compute_trend_raw", "fplcore.metrics.compute", workload, trend),
        _heavy(
            "fixture_features_for_gw",
            "fplcore.metrics.compute",
            f"6 gameweeks, {len(players)} players, {len(world.fixtures_frame)} fixtures",
            fixtures,
            "Python loop over players. Suspected hot spot inside metric compute.",
        ),
        _job(
            "score_and_project",
            "fplcore.metrics.combine",
            f"combined score, availability and projected points for {len(world.cards)} players",
            project,
        ),
    ]


def _optimise_jobs(world: World) -> list[Job]:
    current = {player.id for player in world.opt_players if player.in_squad}
    filtered = _prefilter(world.opt_players, current)
    pool = len(world.opt_players)
    kept = len(filtered)

    def prefilter() -> object:
        players = _prefilter(world.opt_players, current)
        if len(players) < 15:
            raise RuntimeError("prefilter dropped the squad")
        return players

    def solve() -> object:
        return solve_for_transfers(
            filtered,
            bank=200,
            free_transfers=1,
            transfers_in_target=1,
            horizon=1,
            delta=0.85,
        )

    def horizon() -> object:
        return optimise_horizon(
            world.opt_players,
            bank=200,
            free_transfers=1,
            horizon=1,
            max_hits=1,
        )

    plans = {0: _plan(world, 0, 40.0), 1: _plan(world, 1, 43.0), 2: _plan(world, 2, 44.0)}

    def choose() -> object:
        return pick_best_plan(plans, free_transfers=1, settings=HORIZON_SETTINGS[1], max_hits=1)

    def agent_horizons() -> object:
        pages: dict[str, str] = {}
        for horizon in (1, 3, 5):
            solved = optimise_horizon(
                world.opt_players,
                bank=200,
                free_transfers=1,
                horizon=horizon,
            )
            plan = suggestion_from_opt(solved, world.snapshot)
            pages[str(horizon)] = TemplateExplainer().explain(plan)
        if len(pages) != 3 or not all(pages.values()):
            raise RuntimeError("agent horizons did not explain every plan")
        return pages

    return [
        _job(
            "prefilter",
            "fplcore.optimise",
            f"{pool} players, keeping the squad plus {PREFILTER_PER_POSITION} per position ({kept} kept)",
            prefilter,
        ),
        _heavy(
            "solve_for_transfers",
            "fplcore.optimise",
            f"{kept} players after the prefilter, 1 transfer, horizon 1, bank 200, CBC time limit 8s",
            solve,
            "CBC mixed-integer solve. Suspected source of suggestion latency.",
        ),
        _heavy(
            "optimise_horizon",
            "fplcore.optimise",
            f"{pool} players, horizon 1, 1 free transfer, up to 1 hit (solves 0, 1 and 2 transfers)",
            horizon,
            "Request path: prefilter plus one solve per transfer count.",
            repeats=2,
        ),
        _job(
            "pick_best_plan",
            "fplcore.optimise",
            "roll, one transfer and a hit, horizon-1 settings",
            choose,
        ),
        _heavy(
            "agent_horizons",
            "fplcore.optimise",
            f"{pool} players, horizons 1, 3 and 5, then a template explanation",
            agent_horizons,
            "One saved team: the worker solves these three horizons back to back.",
            repeats=2,
        ),
    ]


def _plan(world: World, transfers: int, objective: float) -> SolvedPlan:
    return SolvedPlan(
        transfers_in=transfers,
        hits=max(0, transfers - 1),
        objective=objective,
        projected_gw1=objective,
        squad_ids=list(world.squad_ids),
        xi_ids=list(world.starters),
        bench_ids=list(world.bench),
        captain_id=world.starters[0],
        vice_id=world.starters[1],
        bank_after=20,
    )


def _team_jobs(world: World) -> list[Job]:
    picks = PicksPayload.model_validate(json.loads(world.picks_text))
    merged = merged_from_payloads(world.entry, picks, world.entry_history, world.transfers)
    pairs = [
        (player_id, world.elements_by_id[player_id])
        for player_id in world.squad_ids
        if player_id in world.elements_by_id
    ]

    def snapshot() -> object:
        built = build_snapshot(
            merged=merged,
            players=world.elements_by_id,
            chip_windows=world.bootstrap.chips,
            season_id=world.season_id,
            max_extra_free_transfers=world.bootstrap.game_settings.max_extra_free_transfers,
            overrides={"free_transfers": 2, "bank": 15},
        )
        if not built.content_hash:
            raise RuntimeError("snapshot is missing a content hash")
        return built

    def free_transfers() -> object:
        return derive_free_transfers(
            world.entry_history.current,
            world.entry_history.chips,
            max_extra_free_transfers=world.bootstrap.game_settings.max_extra_free_transfers,
            next_event=world.entry.current_event + 1,
        )

    def selling_prices() -> object:
        return [
            estimate_selling_price(
                player_id=player_id,
                now_cost=element.now_cost,
                cost_change_start=element.cost_change_start,
                transfers=world.transfers,
            )
            for player_id, element in pairs
        ]

    return [
        _job(
            "build_snapshot",
            "fplcore.team_import",
            "one entry: selling prices, free transfers, chips, flags, overrides and the content hash",
            snapshot,
        ),
        _job(
            "derive_free_transfers",
            "fplcore.team_import",
            f"{len(world.entry_history.current)} finished gameweeks",
            free_transfers,
        ),
        _job(
            "estimate_selling_price",
            "fplcore.team_import",
            f"{len(pairs)} squad players scanned against {len(world.transfers)} transfers",
            selling_prices,
            suspect="Scans the full transfer list once per squad player.",
        ),
    ]


def _stats_jobs(world: World) -> list[Job]:
    cards = world.cards
    squad_ids = set(world.squad_ids)
    starter_ids = set(world.starters)
    starters = [world.rows_by_id[player_id] for player_id in world.starters]
    squad_cards = [world.rows_by_id[player_id] for player_id in world.squad_ids]
    count = len(cards)

    def market() -> object:
        return (
            top_transfers(cards),
            price_movers(cards),
            movers_24h(cards, world.yesterday),
            price_pressure(cards, world.manager_count),
        )

    def insights() -> object:
        return (
            in_form(cards),
            finishing_variance(cards),
            differentials(cards),
            defensive_leaders(cards),
            bonus_leaders(cards),
            set_piece_takers(cards),
        )

    def squad() -> object:
        return (
            captaincy_board(starters, {"id": world.starters[0]}),
            template_threats(cards, squad_ids),
            squad_differentials(cards, squad_ids),
            ownership_profile(squad_cards, starter_ids),
        )

    def season() -> object:
        rows = season_rows(world.entry_history.current, world.gameweeks_by_id, world.entry_history.chips)
        return (
            season_summary(rows),
            captain_returns(
                world.entry_history.current,
                world.picks_by_event,
                world.captain_points,
                world.captain_names,
                world.most_captained,
            ),
        )

    def report() -> object:
        projections = xi_projections(world.starters, world.rows_by_id, DEFAULT_WEIGHTS)
        field = [projection_for_row(row, DEFAULT_WEIGHTS) for row in world.rows_by_id.values()]
        return (
            squad_score_for_xi(projections, field),
            xi_expected_points(world.starters, world.rows_by_id, DEFAULT_WEIGHTS),
            performing_players(cards, squad_ids),
            underperforming_players(cards, squad_ids),
            overperforming_players(cards, squad_ids),
        )

    return [
        _job("market_tables", "fplcore.stats.market", f"{count} players", market),
        _heavy(
            "insight_tables",
            "fplcore.stats.insights",
            f"{count} players across form, variance, differentials, defence, bonus and set pieces",
            insights,
            "Pure-Python pass over every player. Profiled to see which table costs the most.",
            repeats=3,
        ),
        _job("squad_tables", "fplcore.stats.squad", f"{count} players, {len(squad_ids)} in the squad", squad),
        _job(
            "season_tables",
            "fplcore.stats.season",
            f"{len(world.entry_history.current)} gameweeks of entry history",
            season,
        ),
        _job(
            "squad_report",
            "fplcore.stats.report",
            f"XI projection and squad score against {count} players",
            report,
        ),
    ]


def _explain_jobs() -> list[Job]:
    rolled = HorizonResult(
        {
            "horizon": 1,
            "transfers": [],
            "hits": 0,
            "gain_vs_roll": -1.5,
            "captain": {"web_name": "Haaland", "proj": 8.4},
            "vice": {"web_name": "Saka"},
            "reason_codes": ["ROLL_PREFERRED", "CAPTAIN_MARGIN"],
        }
    )
    moved = HorizonResult(
        {
            "horizon": 3,
            "transfers": [
                {
                    "out_name": "Salah",
                    "in_name": "Palmer",
                    "metric_deltas": {"form": 0.4, "xgi": 0.2, "fixture": -0.1, "home": 0.05},
                }
            ],
            "hits": 1,
            "gain_vs_roll": 3.2,
            "captain": {"web_name": "Haaland", "proj": 7.1},
            "vice": {"web_name": "Palmer"},
            "reason_codes": ["FORM_UPGRADE", "FIXTURE_SWING", "HIT_NOT_WORTH"],
        }
    )
    results = {"1": rolled, "3": moved, "5": rolled}

    def explain() -> object:
        text = TemplateExplainer().explain_run(results)
        chosen = get_explainer()
        if not text or not chosen.source:
            raise RuntimeError("explainer returned nothing")
        return text

    return [
        _job(
            "explain_run",
            "fplcore.explain",
            "template text for horizons 1, 3 and 5, plus explainer selection",
            explain,
        )
    ]


def _lineup_jobs(world: World) -> list[Job]:
    payload = {
        "starters": list(world.starters),
        "bench": list(world.bench),
        "captain_id": world.starters[0],
        "vice_id": world.starters[1],
        "summary": "Suggested starting XI for the next gameweek.",
    }
    squad_players = []
    for position, player_id in enumerate(world.squad_ids, start=1):
        element = world.elements_by_id[player_id]
        squad_players.append(
            {
                "element": player_id,
                "squad_position": position,
                "team_id": element.team,
                "position_id": element.element_type,
                "web_name": element.web_name,
                "now_cost": element.now_cost,
                "status": element.status,
                "chance_of_playing_next_round": element.chance_of_playing_next_round,
                "news": element.news or "",
            }
        )
    projections = {player_id: 4.5 for player_id in world.squad_ids}

    def lineup() -> object:
        validated = validate_lineup(payload, world.positions, source="optimiser")
        dossier = build_lineup_dossier(
            squad_players, projections, world.team_names, world.fixtures_by_team
        )
        digest = lineup_cache_hash(world.squad_ids, {"form": 0.3, "xgi": 0.35})
        if len(dossier) != 15 or not digest or validated.captain_id != world.starters[0]:
            raise RuntimeError("lineup helpers returned an incomplete result")
        return validated

    return [
        _job(
            "validate_and_dossier",
            "fplcore.lineup",
            "one 15-player squad: validate the XI, build the dossier, hash the weights",
            lineup,
        )
    ]


def _gameweek_jobs(world: World) -> list[Job]:
    def pick() -> object:
        upcoming = pick_upcoming_gameweek(world.gameweeks, world.as_of)
        started = pick_started_gameweek(world.gameweeks, world.as_of)
        if upcoming is None or started is None:
            raise RuntimeError("gameweek selection returned nothing")
        return upcoming, started

    return [
        _job(
            "pick_gameweeks",
            "fplcore.gameweeks",
            f"{len(world.gameweeks)} gameweeks as of {world.as_of.date().isoformat()}",
            pick,
        )
    ]


def _chip_jobs(world: World) -> list[Job]:
    plan = _plan(world, 0, 50.0)
    squad = [player for player in world.opt_players if player.in_squad]
    snapshot = {
        "chips_available": [
            {"name": "bboost", "stop_event": world.next_gw + 1},
            {"name": "3xc", "stop_event": world.next_gw + 8},
        ],
        "selling_prices": {str(player_id): 45 for player_id in world.squad_ids},
    }
    names = {chip["name"] for chip in snapshot["chips_available"]}
    if names & {"freehit", "wildcard"}:
        raise RuntimeError("chip bench must not re-enter the optimiser")

    def chips() -> object:
        return advise_chips(
            snapshot=snapshot,
            best=plan,
            players=squad,
            bank=200,
            next_gw=world.next_gw,
            horizon=1,
        )

    rebuild = {
        "chips_available": [
            {"name": "bboost", "stop_event": world.next_gw + 1},
            {"name": "3xc", "stop_event": world.next_gw + 8},
            {"name": "freehit", "stop_event": world.next_gw + 12},
            {"name": "wildcard", "stop_event": world.next_gw + 12},
        ],
        "selling_prices": {str(player.id): player.sell for player in squad},
    }

    def chip_rebuilds() -> object:
        tips = advise_chips(
            snapshot=rebuild,
            best=plan,
            players=world.opt_players,
            bank=200,
            next_gw=world.next_gw,
            horizon=5,
        )
        found = {tip["chip"] for tip in tips}
        if found != {"bboost", "3xc", "freehit", "wildcard"}:
            raise RuntimeError(f"chip advice missed a chip: {found}")
        return tips

    return [
        _job(
            "advise_chips",
            "fplcore.agent.chips",
            "bench boost and triple captain only, no second squad solve",
            chips,
        ),
        _heavy(
            "chip_rebuilds",
            "fplcore.agent.chips",
            f"horizon 5 with all four chips; free hit and wildcard each solve 16 squads from {len(world.opt_players)} players",
            chip_rebuilds,
            "The signed-in agent does this after the three horizons. Free hit and wildcard rebuild the squad.",
            repeats=2,
        ),
    ]


def _llm_jobs() -> list[Job]:
    source = " ".join(f"player {index} scored {index}.0" for index in range(400))
    text = "player 12 scored 12.0 and player 40 scored 40.0"
    fenced = "```json\n" + json.dumps({"starters": list(range(11)), "summary": "Hold."}) + "\n```"

    def ground() -> object:
        if not grounding_ok(text, source):
            raise RuntimeError("grounding check rejected a number that is in the source")
        return True

    def parse_completion() -> object:
        return _parse_json_content(fenced)

    return [
        _job(
            "grounding_ok",
            "fplcore.llm",
            "every number in a sentence checked against a 400-row source",
            ground,
        ),
        _job(
            "parse_json_content",
            "fplcore.llm",
            "one fenced JSON completion",
            parse_completion,
        ),
    ]


def _api_jobs(world: World) -> list[Job]:
    best = _plan(world, 1, 46.0)
    best.moves = [
        TransferMove(
            out_id=world.bench[0],
            in_id=world.starters[0],
            out_name="Out",
            in_name="In",
            cost_delta=5,
            metric_deltas={"form": 0.2, "xgi": -0.1},
        )
    ]
    solved = {"best": best, "roll": _plan(world, 0, 40.0), "fewer": None, "settings": HORIZON_SETTINGS[1]}
    weights = json.dumps({"form": 0.3, "fixture": 0.25, "home": 0.1, "xgi": 0.35, "value": 0.15})
    bearer = _request(b"Bearer " + b"a" * 40)
    anonymous = _request(b"")

    def shape() -> object:
        body = suggestion_from_opt(solved, world.snapshot)
        view = public_team_view(world.snapshot, squad_score=5.0)
        detailed = with_pitch_details(view["squad_players"], world.team_names, world.fixtures_by_team)
        if not body or not detailed:
            raise RuntimeError("response shaping returned nothing")
        return body

    def weights_query() -> object:
        parsed = parse_weights_query(weights)
        if not parsed:
            raise RuntimeError("weights query parsed empty")
        return parsed

    def limit_key() -> object:
        return limiter_key(bearer), limiter_key(anonymous)

    def digest() -> object:
        return _weights_hash({"form": 0.3, "fixture": 0.25, "home": 0.1, "xgi": 0.35})

    return [
        _job(
            "shape_payloads",
            "api.services",
            "suggestion, public team view and pitch details for one snapshot",
            shape,
        ),
        _job(
            "parse_weights_query",
            "api.weights_query",
            "one JSON weights query string",
            weights_query,
        ),
        _job(
            "limiter_key",
            "api.limiter",
            "one bearer request and one anonymous request",
            limit_key,
        ),
        _job(
            "weights_hash",
            "fplcore.agent.queue",
            "sha256 of a weights dict, the CPU work on the agent queue",
            digest,
        ),
    ]


def _request(authorization: bytes) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/players",
            "raw_path": b"/players",
            "query_string": b"",
            "headers": [(b"authorization", authorization)],
            "client": ("127.0.0.1", 5000),
            "server": ("testserver", 80),
        }
    )


def _db_jobs(world: World) -> list[Job]:
    def helpers() -> object:
        season_id = season_id_from_bootstrap(world.bootstrap)
        windows = retention_windows(world.next_gw)
        points = round_points_from_history(world.summary.history)
        if not season_id or windows.next_gw != world.next_gw:
            raise RuntimeError("retention helpers returned an unexpected window")
        return points

    return [
        _job(
            "pure_helpers",
            "fplcore.db.repos",
            "season id from bootstrap, retention windows, and points from one element summary",
            helpers,
        )
    ]


def _client_jobs(cleanups: list[Callable[[], None]]) -> list[Job]:
    loop = asyncio.new_event_loop()
    cleanups.append(loop.close)
    bucket = TokenBucket(1e12)

    async def _acquire() -> None:
        await bucket.acquire()

    def acquire() -> object:
        loop.run_until_complete(_acquire())
        return None

    return [
        _job(
            "token_bucket_acquire",
            "fplcore.client",
            "one acquire while the bucket has tokens, including the event-loop hop",
            acquire,
        )
    ]


def _settings_jobs() -> list[Job]:
    def load_settings() -> object:
        return Settings().fpl_max_requests_per_second

    return [
        _job(
            "load_settings",
            "fplcore.settings",
            "construct Settings from the environment file",
            load_settings,
        )
    ]
