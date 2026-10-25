from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from fplcore.constants import POSITION_SHORT, SQUAD_MAX_PLAY, SQUAD_MIN_PLAY
from fplcore.llm import LlmError, OpenRouterClient
from fplcore.optimise import PlayerOpt, optimise_horizon
from fplcore.settings import Settings

OPTIMISER_SUMMARY = "Starting XI from projected points for this gameweek."
SUMMARY_LIMIT = 400
# Bumped when XI rules change, so a stored lineup is rebuilt.
LINEUP_RULES_VERSION = 2

LINEUP_SYSTEM = """You pick a Fantasy Premier League starting XI from the 15 players in the squad JSON. You do not recommend transfers.

Rules:
- Use each squad player once. starters has exactly 11 ids. bench has the other 4.
- Formation: exactly 1 goalkeeper, 3 to 5 defenders, 2 to 5 midfielders, 1 to 3 forwards.
- captain_id and vice_id are different starters. The captain scores double. The vice scores as captain only if the captain plays 0 minutes.
- bench order is the autosub order: the goalkeeper first, then outfield players in the order they should come on. An autosub must leave a legal formation.
- Do not start a player with 0 league minutes while another player in the same position has minutes and is available. An easier fixture does not override that.
- Search for injuries, suspensions, press-conference minutes and rotation for these clubs. Do not invent team news. If search is thin, use projected_points, chance_of_playing_next_round, minutes and news.
- Return only JSON: {"starters": [], "bench": [], "captain_id": 0, "vice_id": 0, "summary": "one or two sentences"}.
- summary may only mention players from this squad."""


def lineup_cache_hash(player_ids: list[int], weights: dict[str, Any]) -> str:
    """Identity of a stored XI: the 15 players and the saved weights.

    News, availability and projected points are left out on purpose. A result
    stays until the squad, the weights, the gameweek, or the XI rules change.
    """
    body = {
        "players": sorted(int(player_id) for player_id in player_ids),
        "weights": weights or {},
        "rules": LINEUP_RULES_VERSION,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


class LineupRejected(ValueError):
    """The model returned a lineup that breaks FPL squad rules."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


@dataclass(frozen=True)
class SuggestedLineup:
    starters: list[int]
    bench: list[int]
    captain_id: int
    vice_id: int
    summary: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "starters": list(self.starters),
            "bench": list(self.bench),
            "captain_id": self.captain_id,
            "vice_id": self.vice_id,
            "summary": self.summary,
            "source": self.source,
        }


def build_lineup_dossier(
    squad_players: list[dict[str, Any]],
    projections: dict[int, float],
    team_names: dict[int, str],
    fixtures_by_team: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    dossier: list[dict[str, Any]] = []
    ordered = sorted(squad_players, key=lambda player: int(player.get("squad_position") or 0))
    for player in ordered:
        element = int(player["element"])
        team_id = int(player["team_id"])
        position_id = int(player["position_id"])
        chance = player.get("chance_of_playing_next_round")
        dossier.append(
            {
                "id": element,
                "name": player.get("web_name") or "",
                "club": team_names.get(team_id, ""),
                "position": POSITION_SHORT.get(position_id, ""),
                "price": round(int(player.get("now_cost") or 0) / 10, 1),
                "status": player.get("status") or "",
                "chance_of_playing_next_round": None if chance is None else int(chance),
                "news": player.get("news") or "",
                "minutes": int(player.get("minutes") or 0),
                "starts": int(player.get("starts") or 0),
                "fixtures": fixtures_by_team.get(team_id, []),
                "projected_points": round(float(projections.get(element, 0.0)), 2),
            }
        )
    return dossier


def _id_list(value: Any, label: str, reasons: list[str]) -> list[int]:
    if not isinstance(value, list):
        reasons.append(f"{label} must be a list of player ids")
        return []
    ids: list[int] = []
    for item in value:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            reasons.append(f"{label} contains a non-numeric id")
    return ids


def _required_id(payload: dict[str, Any], key: str, reasons: list[str]) -> int | None:
    try:
        return int(payload[key])
    except (KeyError, TypeError, ValueError):
        reasons.append(f"{key} must be a player id")
        return None


def validate_lineup(
    payload: dict[str, Any],
    positions: dict[int, int],
    *,
    source: str = "llm",
) -> SuggestedLineup:
    """Reject a lineup that is not a legal partition of this 15-man squad."""
    reasons: list[str] = []
    starters = _id_list(payload.get("starters"), "starters", reasons)
    bench = _id_list(payload.get("bench"), "bench", reasons)
    captain_id = _required_id(payload, "captain_id", reasons)
    vice_id = _required_id(payload, "vice_id", reasons)
    squad_ids = set(positions)
    starter_ids = set(starters)
    bench_ids = set(bench)

    if len(starters) != 11 or len(starter_ids) != 11:
        reasons.append("starters must be 11 different players")
    if len(bench) != 4 or len(bench_ids) != 4:
        reasons.append("bench must be 4 different players")
    if starter_ids & bench_ids:
        reasons.append("a player cannot start and sit on the bench")
    if (starter_ids | bench_ids) - squad_ids:
        reasons.append("lineup includes a player outside the squad")
    if squad_ids - (starter_ids | bench_ids):
        reasons.append("lineup must use every squad player")

    counts = {pos: 0 for pos in SQUAD_MIN_PLAY}
    for player_id in starter_ids & squad_ids:
        counts[positions[player_id]] = counts.get(positions[player_id], 0) + 1
    for pos, minimum in SQUAD_MIN_PLAY.items():
        if counts.get(pos, 0) < minimum:
            reasons.append(f"not enough {POSITION_SHORT.get(pos, str(pos))} starters")
    for pos, maximum in SQUAD_MAX_PLAY.items():
        if counts.get(pos, 0) > maximum:
            reasons.append(f"too many {POSITION_SHORT.get(pos, str(pos))} starters")

    if captain_id is not None and captain_id not in starter_ids:
        reasons.append("captain must start")
    if vice_id is not None and vice_id not in starter_ids:
        reasons.append("vice must start")
    if captain_id is not None and captain_id == vice_id:
        reasons.append("captain and vice must be different players")
    if bench and any(positions.get(player_id) == 1 for player_id in bench_ids) and positions.get(bench[0]) != 1:
        reasons.append("bench goalkeeper must be first")

    if reasons or captain_id is None or vice_id is None:
        raise LineupRejected(reasons or ["lineup is incomplete"])

    summary = payload.get("summary") or ""
    if not isinstance(summary, str):
        summary = ""
    summary = " ".join(summary.split())
    if len(summary) > SUMMARY_LIMIT:
        summary = summary[:SUMMARY_LIMIT].rstrip()
    if not summary:
        summary = "Suggested starting XI for the next gameweek."
    return SuggestedLineup(
        starters=starters,
        bench=bench,
        captain_id=captain_id,
        vice_id=vice_id,
        summary=summary,
        source=source,
    )


def _listed_minutes(player: dict[str, Any]) -> int | None:
    if "minutes" not in player:
        return None
    try:
        return int(player["minutes"])
    except (TypeError, ValueError):
        return None


def _available(player: dict[str, Any]) -> bool:
    status = str(player.get("status") or "a")
    if status in {"i", "s", "u", "n"}:
        return False
    chance = player.get("chance_of_playing_next_round")
    if chance is None:
        return status == "a"
    try:
        return int(chance) > 0
    except (TypeError, ValueError):
        return False


def unused_starter_reasons(starters: list[int], dossier: list[dict[str, Any]]) -> list[str]:
    """A player with no league minutes does not start ahead of a fit regular."""
    by_id = {int(player["id"]): player for player in dossier if "id" in player}
    reasons: list[str] = []
    for starter_id in starters:
        player = by_id.get(starter_id)
        if player is None:
            continue
        minutes = _listed_minutes(player)
        if minutes is None or minutes > 0:
            continue
        position = player.get("position")
        regular = next(
            (
                other
                for other in dossier
                if int(other.get("id") or 0) != starter_id
                and other.get("position") == position
                and (_listed_minutes(other) or 0) > 0
                and _available(other)
            ),
            None,
        )
        if regular is None:
            continue
        name = player.get("name") or str(starter_id)
        other_name = regular.get("name") or str(regular.get("id"))
        reasons.append(f"{name} has not played; start {other_name} instead")
    return reasons


def lineup_from_optimiser(players: list[PlayerOpt]) -> SuggestedLineup:
    """Pick the XI with the transfer solver locked to zero transfers."""
    solved = optimise_horizon(players, bank=0, free_transfers=0, horizon=1, max_hits=0)
    best = solved["best"]
    positions = {player.id: player.position_id for player in players}
    return validate_lineup(
        {
            "starters": best.xi_ids,
            "bench": best.bench_ids,
            "captain_id": best.captain_id,
            "vice_id": best.vice_id,
            "summary": OPTIMISER_SUMMARY,
        },
        positions,
        source="optimiser",
    )


async def choose_lineup(
    players: list[PlayerOpt],
    dossier: list[dict[str, Any]],
    *,
    settings: Settings,
    allow_llm: bool,
    client: OpenRouterClient | None = None,
) -> SuggestedLineup:
    """Ask the model for a searched XI, then keep a legal optimiser XI if that fails."""
    if not allow_llm or not settings.llm_api_key or not settings.llm_model:
        return lineup_from_optimiser(players)
    llm = client or OpenRouterClient(settings)
    close_client = client is None
    try:
        return await _lineup_from_model(llm, players, dossier)
    finally:
        if close_client:
            await llm.aclose()


async def _lineup_from_model(
    client: OpenRouterClient,
    players: list[PlayerOpt],
    dossier: list[dict[str, Any]],
) -> SuggestedLineup:
    positions = {player.id: player.position_id for player in players}
    user = json.dumps({"squad": dossier}, default=str)
    try:
        raw = await client.chat_with_search(system=LINEUP_SYSTEM, user=user)
    except LlmError:
        return lineup_from_optimiser(players)
    try:
        return _accept_model_lineup(raw, positions, dossier)
    except LineupRejected as exc:
        repair = json.dumps(
            {
                "squad": dossier,
                "rejected": raw,
                "errors": exc.reasons,
                "instruction": "Return corrected JSON for this same squad. Do not search.",
            },
            default=str,
        )
    try:
        fixed = await client.chat_json(system=LINEUP_SYSTEM, user=repair)
    except LlmError:
        return lineup_from_optimiser(players)
    try:
        return _accept_model_lineup(fixed, positions, dossier)
    except LineupRejected:
        return lineup_from_optimiser(players)


def _accept_model_lineup(
    payload: dict[str, Any],
    positions: dict[int, int],
    dossier: list[dict[str, Any]],
) -> SuggestedLineup:
    lineup = validate_lineup(payload, positions)
    reasons = unused_starter_reasons(lineup.starters, dossier)
    if reasons:
        raise LineupRejected(reasons)
    return lineup
