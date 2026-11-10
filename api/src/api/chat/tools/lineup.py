"""Suggested XI from the stored lineup or a zero-transfer solve. No web search."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from api.chat.tools.common import NoArgs, ok
from api.chat.tools.reading import lookup_as_of, no_team, user_snapshot
from api.services import load_opt_players
from fplcore.chat.cache import current_cache
from fplcore.chat.registry import BoundTool
from fplcore.chat.types import ToolContext, ToolResult, failure
from fplcore.constants import DEFAULT_WEIGHTS
from fplcore.db.repos import get_suggested_lineup
from fplcore.db.stats_repo import next_gw_id
from fplcore.lineup import (
    LineupRejected,
    SuggestedLineup,
    lineup_cache_hash,
    lineup_from_optimiser,
    validate_lineup,
)
from fplcore.optimise import PlayerOpt


def _run(ctx: ToolContext, args: BaseModel, conn: Any) -> ToolResult:
    del args
    payload = lineup_payload(ctx, conn)
    if isinstance(payload, ToolResult):
        return payload
    return ok(payload, as_of=lookup_as_of(conn), data_version=ctx.data_version)


def lineup_payload(ctx: ToolContext, conn: Any) -> dict[str, Any] | ToolResult:
    cache = current_cache()
    if cache is not None and cache.lineup_loaded:
        if cache.lineup is None:
            return failure("NO_SOLUTION", "The lineup could not be built.", hint="Use get_my_team.")
        return cache.lineup
    payload = _compute(ctx, conn)
    if cache is not None:
        cache.lineup_loaded = True
        cache.lineup = payload if isinstance(payload, dict) else None
    return payload


def _compute(ctx: ToolContext, conn: Any) -> dict[str, Any] | ToolResult:
    snapshot = user_snapshot(ctx, conn)
    if snapshot is None:
        return no_team()
    weights = ctx.weights or DEFAULT_WEIGHTS
    squad = [player for player in load_opt_players(conn, snapshot, weights, 1) if player.in_squad]
    if len(squad) != 15:
        return failure("NO_SOLUTION", "The squad is not 15 players.", hint="Import the team again.")
    positions = {player.id: player.position_id for player in squad}
    lineup = _cached(conn, ctx, snapshot, weights, positions) or _solved(squad)
    if lineup is None:
        return failure("NO_SOLUTION", "The lineup could not be built.", hint="Use get_my_team.")
    return _body(lineup, squad, snapshot.picks)


def _cached(
    conn: Any,
    ctx: ToolContext,
    snapshot: Any,
    weights: dict[str, float],
    positions: dict[int, int],
) -> SuggestedLineup | None:
    try:
        gameweek = next_gw_id(conn, snapshot.season_id)
    except RuntimeError:
        return None
    player_ids = [int(pick["element"]) for pick in snapshot.picks]
    stored = get_suggested_lineup(
        conn,
        ctx.user_id,
        int(snapshot.entry_id),
        gameweek,
        lineup_cache_hash(player_ids, weights),
    )
    if not stored:
        return None
    try:
        return validate_lineup(stored, positions, source=str(stored.get("source") or "cache"))
    except LineupRejected:
        return None


def _solved(squad: list[PlayerOpt]) -> SuggestedLineup | None:
    try:
        return lineup_from_optimiser(squad)
    except (LineupRejected, ValueError, RuntimeError):
        return None


def _body(lineup: SuggestedLineup, squad: list[PlayerOpt], picks: list[dict[str, Any]]) -> dict[str, Any]:
    proj = {player.id: round(player.proj[0], 2) if player.proj else 0.0 for player in squad}
    positions = {player.id: player.position_id for player in squad}
    published_xi, _bench = _published(picks)
    return {
        "formation": _formation(lineup.starters, positions),
        "xi": lineup.starters,
        "bench": lineup.bench,
        "captain_id": lineup.captain_id,
        "vice_id": lineup.vice_id,
        "changes_vs_current": _changes(lineup, published_xi, proj, positions),
    }


def _formation(starters: list[int], positions: dict[int, int]) -> str:
    counts = {2: 0, 3: 0, 4: 0}
    for player_id in starters:
        position = positions.get(player_id)
        if position in counts:
            counts[position] += 1
    return f"{counts[2]}-{counts[3]}-{counts[4]}"


def _published(picks: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    ordered = sorted(picks, key=lambda pick: int(pick.get("position") or 99))
    xi = [int(pick["element"]) for pick in ordered if int(pick.get("position") or 99) <= 11]
    bench = [int(pick["element"]) for pick in ordered if int(pick.get("position") or 99) > 11]
    return xi, bench


def _changes(
    lineup: SuggestedLineup,
    published_xi: list[int],
    proj: dict[int, float],
    positions: dict[int, int],
) -> list[dict[str, Any]]:
    published = set(published_xi)
    suggested = set(lineup.starters)
    changes: list[dict[str, Any]] = []
    incoming = [player_id for player_id in lineup.starters if player_id not in published]
    outgoing = [player_id for player_id in published_xi if player_id not in suggested]
    used: set[int] = set()
    for player_id in incoming:
        replaced = next(
            (
                other
                for other in outgoing
                if other not in used and positions.get(other) == positions.get(player_id)
            ),
            None,
        )
        if replaced is None:
            replaced = next((other for other in outgoing if other not in used), None)
        delta = None
        if replaced is not None:
            used.add(replaced)
            delta = round(proj.get(player_id, 0.0) - proj.get(replaced, 0.0), 2)
        changes.append({"id": player_id, "to": "xi", "proj": proj.get(player_id, 0.0), "delta": delta})
    for player_id in lineup.bench:
        if player_id in published:
            changes.append({"id": player_id, "to": "bench", "proj": proj.get(player_id, 0.0), "delta": None})
    return changes[:6]


get_best_lineup = BoundTool(
    name="get_best_lineup",
    description="Suggested XI, bench order, captain and the players who differ from the published picks, with the projection difference.",
    args_model=NoArgs,
    handler=_run,
    timeout_s=15.0,
)
