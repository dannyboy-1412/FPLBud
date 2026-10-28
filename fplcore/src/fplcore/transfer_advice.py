from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, replace
from typing import Any

from fplcore.constants import POSITION_SHORT
from fplcore.llm import LlmError, OpenRouterClient
from fplcore.optimise import PlayerOpt, SolvedPlan, TransferMove, optimise_horizon
from fplcore.settings import Settings

SUMMARY_LIMIT = 400
PLAN_HORIZON = 3
MAX_FREE_TRANSFERS = 5
# Bumped when the transfer rules change, so a stored plan is rebuilt.
TRANSFER_RULES_VERSION = 3
# How sharply a points gap becomes a recommendation share. One point of
# net value is a clear lean, not a coin toss.
RECOMMENDATION_TEMPERATURE = 0.9
# A shown alternative stays visible even when the points gap is wide.
MIN_OPTION_PCT = 8
MAX_SHOWN_OPTIONS = 4
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BARE_URL = re.compile(r"https?://\S+")
_SOURCE_PAREN = re.compile(r"\s*\([^()]*\.(?:com|app|co\.uk|org|net|io)[^()]*\)")

# A banked free transfer is worth the hit it can save later, but that value
# falls once two are already saved: only five can be banked, and two or three
# is the range top managers actually want. The last free transfer is the
# expensive one, because spending it leaves none for next week.
THRESHOLD_WHEN_TWO_OR_MORE_REMAIN = 1.0
THRESHOLD_WHEN_ONE_REMAINS = 1.5
THRESHOLD_WHEN_NONE_REMAIN = 2.5
# An absent starter can be sold even when the move is slightly down on paper.
ABSENCE_OBJECTIVE_SLACK = 0.25

TRANSFER_SYSTEM = """You decide this gameweek's Fantasy Premier League transfers. You think like a manager who finishes in the top 50.

How those managers transfer:
- Roll is the default. A free transfer is an asset. With one, bank it unless a move is clearly better than having two next week. With two or three, make only the moves that are obvious and leave the rest banked. With four or five, do not sit on transfers that cannot be banked, and still do not make a sideways move.
- A clear move removes a player who will not play, or it is a real upgrade across the next few weeks: nailed minutes, a fixture run, or the underlying numbers. One awkward fixture is not a reason to sell. Last week's points are not a reason to buy.
- Do not take a points hit. Never use more transfers than free_transfers.
- Do not chase a price rise. Team news is worth more than moving early.
- Search for injuries, suspensions, press-conference minutes and rotation for the clubs named below. Do not invent team news. If search is thin, keep the recommended alternative.
- alternatives are the best legal sets for each number of transfers. Choose one of them. Do not name a player who is not in that set.
- A quieter alternative, including a roll, is always allowed. A busier one is only for when search confirms a squad player will not play and that alternative sells them.
- Return only JSON: {"action": "roll" or "transfer", "moves": [{"out_id": 0, "in_id": 0}], "summary": "one or two sentences"}.
- For a roll, moves is []. summary says to roll. summary may only mention players named in this payload, and it must not invent prices or points."""


class TransferRejected(ValueError):
    """The model chose a transfer set the rules do not allow."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def _move_dict(move: TransferMove) -> dict[str, Any]:
    return {
        "out_id": move.out_id,
        "in_id": move.in_id,
        "out_name": move.out_name,
        "in_name": move.in_name,
    }


@dataclass(frozen=True)
class TransferSuggestion:
    action: str
    free_transfers: int
    moves: list[TransferMove]
    summary: str
    source: str
    starters: list[int] = field(default_factory=list)
    bench: list[int] = field(default_factory=list)
    captain_id: int | None = None
    vice_id: int | None = None
    options: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        moves = [_move_dict(move) for move in self.moves]
        options = [dict(option) for option in self.options] or [
            {
                "action": self.action,
                "moves": moves,
                "recommended_pct": 100,
                "reason": self.summary,
                "chosen": True,
                "starters": list(self.starters),
                "bench": list(self.bench),
                "captain_id": self.captain_id,
                "vice_id": self.vice_id,
                "incomings": [],
            }
        ]
        return {
            "action": self.action,
            "free_transfers": self.free_transfers,
            "moves": moves,
            "starters": list(self.starters),
            "bench": list(self.bench),
            "captain_id": self.captain_id,
            "vice_id": self.vice_id,
            "summary": self.summary,
            "source": self.source,
            "options": options,
        }


def transfer_cache_hash(
    player_ids: list[int],
    weights: dict[str, Any],
    free_transfers: int,
    bank: int,
    selling_prices: dict[Any, Any],
) -> str:
    """Identity of a stored transfer plan.

    News and projected points are left out. A result stays until the squad,
    the weights, the bank, the free transfers, the selling prices, or the
    transfer rules change.
    """
    selling = {str(int(key)): int(value) for key, value in selling_prices.items()}
    body = {
        "players": sorted(int(player_id) for player_id in player_ids),
        "weights": weights or {},
        "free_transfers": int(free_transfers),
        "bank": int(bank),
        "selling": selling,
        "rules": TRANSFER_RULES_VERSION,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def option_cost(free_transfers: int, used: int) -> float:
    """What the spent free transfers are worth if they are kept instead.

    Transfers are spent from the spare end. Going from five to four is cheap.
    Spending the last one is not, because next week then starts on one.
    """
    cost = 0.0
    available = max(0, int(free_transfers))
    for step in range(1, max(0, int(used)) + 1):
        remaining = available - step
        if remaining >= 2:
            cost += THRESHOLD_WHEN_TWO_OR_MORE_REMAIN
        elif remaining == 1:
            cost += THRESHOLD_WHEN_ONE_REMAINS
        else:
            cost += THRESHOLD_WHEN_NONE_REMAIN
    return cost


def _net(plan: SolvedPlan, free_transfers: int) -> float:
    return plan.objective - option_cost(free_transfers, plan.transfers_in)


def _pairs(plan: SolvedPlan) -> frozenset[tuple[int, int]]:
    return frozenset((move.out_id, move.in_id) for move in plan.moves)


def _chance(note: dict[str, Any] | None) -> int | None:
    if note is None:
        return None
    chance = note.get("chance_of_playing_next_round")
    if chance is None:
        return None
    try:
        return int(chance)
    except (TypeError, ValueError):
        return None


def _unavailable(note: dict[str, Any]) -> bool:
    status = str(note.get("status") or "a")
    if status in {"i", "s", "u"}:
        return True
    chance = note.get("chance_of_playing_next_round")
    if chance is None:
        return False
    try:
        return int(chance) == 0
    except (TypeError, ValueError):
        return False


def unavailable_starter_ids(notes: list[dict[str, Any]], starter_ids: list[int]) -> set[int]:
    """Squad players who will not play and who are still in the rolled-out XI."""
    starters = set(starter_ids)
    found: set[int] = set()
    for note in notes:
        try:
            player_id = int(note["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if player_id in starters and _unavailable(note):
            found.add(player_id)
    return found


def _absence_fix(plan: SolvedPlan, roll: SolvedPlan, free_transfers: int, absent: set[int]) -> bool:
    if not _fixes_absence(plan, absent):
        return False
    holds_value = plan.objective >= roll.objective - ABSENCE_OBJECTIVE_SLACK
    return holds_value or _net(plan, free_transfers) >= _net(roll, free_transfers)


def _fixes_absence(plan: SolvedPlan, absent: set[int]) -> bool:
    if not absent or plan.transfers_in == 0:
        return False
    sold = {move.out_id for move in plan.moves}
    return absent <= sold


def _joined(names: list[str]) -> str:
    if not names:
        return "A player"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def _banked_sentence(spare: int) -> str:
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four"}
    word = words.get(spare, str(spare))
    if spare == 1:
        return f"{word} free transfer stays in the bank."
    return f"{word} free transfers stay in the bank."


def _trade(moves: list[TransferMove]) -> str:
    parts = [f"{move.out_name} for {move.in_name}" for move in moves]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f" and {parts[-1]}"


def _move_clause(moves: list[TransferMove]) -> str:
    parts = [f"sell {move.out_name} for {move.in_name}" for move in moves]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f" and {parts[-1]}"


def _sentence(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return text
    return text[0].upper() + text[1:]


def summarise(
    plan: SolvedPlan,
    free_transfers: int,
    *,
    absent_starters: set[int],
    names: dict[int, str],
) -> str:
    spare = max(0, free_transfers - plan.transfers_in)
    if plan.transfers_in == 0 or not plan.moves:
        if free_transfers <= 0:
            return "No free transfer this week, so roll."
        if absent_starters:
            label = _joined([names.get(player_id, "A player") for player_id in sorted(absent_starters)])
            verb = "is" if len(absent_starters) == 1 else "are"
            return f"Roll. {label} {verb} out, and no replacement is a clear upgrade."
        if free_transfers == 1:
            return "Roll the free transfer. No move is clear enough, and banking it leaves two next week."
        if free_transfers == 2:
            return "Roll both free transfers. No move is a clear upgrade."
        return f"Roll all {free_transfers} free transfers. No move is a clear upgrade."

    forced = len(plan.moves) == 1 and plan.moves[0].out_id in absent_starters
    if forced:
        move = plan.moves[0]
        lead = f"{move.out_name} is out, so sell {move.out_name} for {move.in_name}."
    elif spare == 0 and len(plan.moves) > 1:
        opening = "Use both free transfers" if len(plan.moves) == 2 else f"Use all {len(plan.moves)} free transfers"
        return _sentence(f"{opening}: {_move_clause(plan.moves)}.")
    else:
        lead = _sentence(f"{_move_clause(plan.moves)}.")

    if spare == 0:
        return f"{lead} That uses the free transfer."
    return f"{lead} {_banked_sentence(spare)}"


def _candidate_plans(plans: dict[int, SolvedPlan], free_transfers: int) -> dict[int, SolvedPlan]:
    kept: dict[int, SolvedPlan] = {}
    for count, plan in plans.items():
        if plan.hits > 0 or plan.transfers_in != count:
            continue
        if count < 0 or count > free_transfers:
            continue
        if count > 0 and len(plan.moves) != count:
            continue
        kept[count] = plan
    return kept


def _shares(nets: dict[int, float]) -> dict[int, int]:
    if not nets:
        return {}
    if len(nets) == 1:
        return {next(iter(nets)): 100}
    peak = max(nets.values())
    weights = {
        key: math.exp((net - peak) / RECOMMENDATION_TEMPERATURE) for key, net in nets.items()
    }
    total = sum(weights.values()) or 1.0
    raw = {key: 100 * weight / total for key, weight in weights.items()}
    floors = {key: int(value) for key, value in raw.items()}
    leftover = 100 - sum(floors.values())
    order = sorted(raw, key=lambda key: (raw[key] - floors[key], raw[key]), reverse=True)
    for key in order[:leftover]:
        floors[key] += 1
    return _lift_floor(floors)


def _lift_floor(shares: dict[int, int]) -> dict[int, int]:
    if len(shares) < 2:
        return shares
    floor = min(MIN_OPTION_PCT, max(1, (100 // len(shares)) - 1))
    lifted = {key: max(value, floor) for key, value in shares.items()}
    overflow = sum(lifted.values()) - 100
    donors = sorted(lifted, key=lambda key: lifted[key], reverse=True)
    for key in donors:
        if overflow <= 0:
            break
        spare = lifted[key] - floor
        take = min(spare, overflow)
        lifted[key] -= take
        overflow -= take
    return lifted


def _shares_for_choice(nets: dict[int, float], chosen_key: int) -> dict[int, int]:
    adjusted = dict(nets)
    others = [net for key, net in nets.items() if key != chosen_key]
    if others and adjusted.get(chosen_key, 0.0) <= max(others):
        adjusted[chosen_key] = max(others) + 1.2
    return _shares(adjusted)


def _best_transfer(legal: dict[int, SolvedPlan], free_transfers: int) -> SolvedPlan | None:
    transfers = [plan for count, plan in legal.items() if count > 0]
    if not transfers:
        return None
    return max(transfers, key=lambda plan: (_net(plan, free_transfers), -plan.transfers_in))


def _option_reason(
    plan: SolvedPlan,
    *,
    chosen: bool,
    free_transfers: int,
    absent: set[int],
    rival: SolvedPlan | None,
    beats_roll: bool,
) -> str:
    if plan.transfers_in == 0 or not plan.moves:
        if rival is None or not rival.moves:
            if free_transfers <= 0:
                return "No free transfer this week. Roll."
            return "No move is worth making. Keep the free transfer for next week."
        trade = _trade(list(rival.moves))
        if absent and chosen:
            label = _joined(sorted({move.out_name for move in rival.moves if move.out_id in absent}) or ["A player"])
            verb = "is" if len(absent) == 1 else "are"
            return f"Roll. {label} {verb} out, and selling {trade} is not a clear fix."
        if chosen:
            return f"Bank the free transfer. Selling {trade} does not improve the starting XI enough to spend it."
        return (
            f"Bank the free transfer instead of selling {trade}. "
            "A saved transfer covers a later injury without a hit."
        )

    lead = _sentence(f"{_move_clause(list(plan.moves))}.")
    if len(plan.moves) == 1 and plan.moves[0].out_id in absent:
        return f"{plan.moves[0].out_name} is out of the side. {lead}"
    if chosen:
        spare = max(0, free_transfers - plan.transfers_in)
        if spare:
            return f"{lead} {_banked_sentence(spare)} This is a clear upgrade."
        return f"{lead} This is a clear upgrade, so use the free transfer."
    if beats_roll:
        return f"{lead} A real gain, and still behind the recommended move."
    return f"{lead} It does not improve the starting XI enough to spend a free transfer."


def _build_options(
    legal: dict[int, SolvedPlan],
    *,
    chosen: SolvedPlan,
    free_transfers: int,
    absent: set[int],
    chosen_reason: str | None,
) -> tuple[dict[str, Any], ...]:
    if not legal:
        return ()
    chosen_key = chosen.transfers_in if chosen.transfers_in in legal else 0
    if chosen_key in legal and _pairs(legal[chosen_key]) != _pairs(chosen) and chosen.transfers_in == 0:
        chosen_key = 0
    nets = {count: _net(plan, free_transfers) for count, plan in legal.items()}
    ranked = sorted(legal, key=lambda count: (nets[count], -count), reverse=True)
    shown_keys = ranked[:MAX_SHOWN_OPTIONS]
    if chosen_key not in shown_keys:
        shown_keys = [chosen_key, *shown_keys[: MAX_SHOWN_OPTIONS - 1]]
    shown = {key: legal[key] for key in shown_keys}
    pcts = _shares_for_choice({key: nets[key] for key in shown}, chosen_key)
    rival = _best_transfer(shown, free_transfers)
    options: list[dict[str, Any]] = []
    for count, plan in sorted(shown.items(), key=lambda item: pcts[item[0]], reverse=True):
        is_chosen = count == chosen_key and _pairs(plan) == _pairs(legal.get(chosen_key, plan))
        roll = shown.get(0)
        beats_roll = roll is not None and _net(plan, free_transfers) >= _net(roll, free_transfers)
        reason = chosen_reason if is_chosen and chosen_reason else _option_reason(
            plan,
            chosen=is_chosen,
            free_transfers=free_transfers,
            absent=absent,
            rival=rival,
            beats_roll=beats_roll,
        )
        action = "transfer" if plan.moves and plan.transfers_in > 0 else "roll"
        options.append(
            {
                "action": action,
                "moves": [] if action == "roll" else [_move_dict(move) for move in plan.moves],
                "recommended_pct": pcts[count],
                "reason": reason,
                "chosen": is_chosen,
                "starters": list(plan.xi_ids),
                "bench": list(plan.bench_ids),
                "captain_id": plan.captain_id,
                "vice_id": plan.vice_id,
            }
        )
    return tuple(options)


def _with_options(
    suggestion: TransferSuggestion,
    legal: dict[int, SolvedPlan],
    *,
    chosen: SolvedPlan,
    absent: set[int],
    chosen_reason: str | None,
) -> TransferSuggestion:
    return replace(
        suggestion,
        options=_build_options(
            legal,
            chosen=chosen,
            free_transfers=suggestion.free_transfers,
            absent=absent,
            chosen_reason=chosen_reason,
        ),
    )


def advice_from_plans(
    plans: dict[int, SolvedPlan],
    *,
    free_transfers: int,
    unavailable_ids: set[int],
    names: dict[int, str] | None = None,
    source: str = "policy",
) -> TransferSuggestion:
    """Pick a roll or a set of free transfers the way a top manager would.

    Hits are never suggested. A move has to beat the value of keeping that
    free transfer. The exception is a starter who will not play: sell them
    when a legal replacement holds the squad's points up.
    """
    available = max(0, min(MAX_FREE_TRANSFERS, int(free_transfers)))
    legal = _candidate_plans(plans, available)
    roll = legal.get(0) or plans.get(0)
    if roll is None:
        raise ValueError("roll plan (0 transfers) is required")
    labels = names or {}
    absent = unavailable_ids & set(roll.xi_ids)

    def rank(plan: SolvedPlan) -> tuple[float, int]:
        return (_net(plan, available), -plan.transfers_in)

    chosen = max(legal.values(), key=rank) if legal else roll
    if absent and not _fixes_absence(chosen, absent):
        fixes = [plan for plan in legal.values() if _absence_fix(plan, roll, available, absent)]
        clearing = [plan for plan in fixes if _net(plan, available) >= _net(roll, available)]
        if clearing:
            chosen = max(clearing, key=rank)
        elif fixes:
            chosen = min(fixes, key=lambda plan: (plan.transfers_in, -plan.objective))

    if chosen.transfers_in == 0 or not chosen.moves:
        chosen = roll
    summary = summarise(chosen, available, absent_starters=absent, names=labels)
    action = "transfer" if chosen.moves and chosen.transfers_in > 0 else "roll"
    return _with_options(
        TransferSuggestion(
            action=action,
            free_transfers=available,
            moves=list(chosen.moves) if action == "transfer" else [],
            summary=summary,
            source=source,
            starters=list(chosen.xi_ids),
            bench=list(chosen.bench_ids),
            captain_id=chosen.captain_id,
            vice_id=chosen.vice_id,
        ),
        legal,
        chosen=chosen,
        absent=absent,
        chosen_reason=None,
    )


def _allowed(
    plan: SolvedPlan,
    policy: TransferSuggestion,
    roll: SolvedPlan,
    free_transfers: int,
    absent: set[int],
) -> bool:
    if plan.hits > 0 or plan.transfers_in > free_transfers:
        return False
    if plan.transfers_in == 0:
        return True
    if _pairs(plan) == _policy_pairs(policy):
        return True
    if plan.transfers_in < len(policy.moves):
        return _net(plan, free_transfers) >= _net(roll, free_transfers) or _fixes_absence(plan, absent)
    return _net(plan, free_transfers) >= _net(roll, free_transfers)


def _policy_pairs(policy: TransferSuggestion) -> frozenset[tuple[int, int]]:
    return frozenset((move.out_id, move.in_id) for move in policy.moves)


def _plain_prose(value: str) -> str:
    text = _MARKDOWN_LINK.sub(r"\1", value)
    text = _BARE_URL.sub("", text)
    text = _SOURCE_PAREN.sub("", text)
    return " ".join(text.split()).strip()


def _clean_summary(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    summary = _plain_prose(value)
    if not summary:
        return fallback
    if len(summary) > SUMMARY_LIMIT:
        return summary[:SUMMARY_LIMIT].rstrip()
    return summary


def _parsed_moves(payload: dict[str, Any], reasons: list[str]) -> list[tuple[int, int]] | None:
    raw = payload.get("moves")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        reasons.append("moves must be a list")
        return None
    pairs: list[tuple[int, int]] = []
    for item in raw:
        if not isinstance(item, dict):
            reasons.append("each move must name an out_id and an in_id")
            continue
        try:
            pairs.append((int(item["out_id"]), int(item["in_id"])))
        except (KeyError, TypeError, ValueError):
            reasons.append("each move must name an out_id and an in_id")
    return pairs


def advice_from_model(
    payload: dict[str, Any],
    plans: dict[int, SolvedPlan],
    *,
    policy: TransferSuggestion,
    free_transfers: int,
    unavailable_ids: set[int],
    names: dict[int, str],
) -> TransferSuggestion:
    """Keep a model choice only when it is one of the legal alternatives."""
    reasons: list[str] = []
    action = str(payload.get("action") or "").strip().lower()
    pairs = _parsed_moves(payload, reasons)
    if pairs is None:
        raise TransferRejected(reasons)
    if action not in {"roll", "transfer"}:
        reasons.append("action must be roll or transfer")
    if action == "roll" and pairs:
        reasons.append("a roll has no moves")
    if action == "transfer" and not pairs:
        reasons.append("a transfer needs moves")
    if reasons:
        raise TransferRejected(reasons)

    legal = _candidate_plans(plans, free_transfers)
    roll = legal.get(0)
    if roll is None:
        raise TransferRejected(["roll plan is missing"])
    absent = unavailable_ids & set(roll.xi_ids)

    if action == "roll":
        fallback = summarise(roll, free_transfers, absent_starters=absent, names=names)
        summary = _clean_summary(payload.get("summary"), fallback)
        return _with_options(
            TransferSuggestion(
                action="roll",
                free_transfers=free_transfers,
                moves=[],
                summary=summary,
                source="llm",
                starters=list(roll.xi_ids),
                bench=list(roll.bench_ids),
                captain_id=roll.captain_id,
                vice_id=roll.vice_id,
            ),
            legal,
            chosen=roll,
            absent=absent,
            chosen_reason=summary,
        )

    wanted = frozenset(pairs)
    if len(wanted) != len(pairs):
        raise TransferRejected(["moves must be different transfers"])
    match = next((plan for plan in legal.values() if _pairs(plan) == wanted), None)
    if match is None:
        raise TransferRejected(["moves must be one of the alternatives"])
    if not _allowed(match, policy, roll, free_transfers, absent):
        raise TransferRejected(["that alternative is not a clear move"])

    fallback = summarise(match, free_transfers, absent_starters=absent, names=names)
    summary = _clean_summary(payload.get("summary"), fallback)
    return _with_options(
        TransferSuggestion(
            action="transfer",
            free_transfers=free_transfers,
            moves=list(match.moves),
            summary=summary,
            source="llm",
            starters=list(match.xi_ids),
            bench=list(match.bench_ids),
            captain_id=match.captain_id,
            vice_id=match.vice_id,
        ),
        legal,
        chosen=match,
        absent=absent,
        chosen_reason=summary,
    )


def _brief(
    player: PlayerOpt,
    team_names: dict[int, str],
    fixtures_by_team: dict[int, list[dict[str, Any]]],
    note: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "id": player.id,
        "name": player.web_name,
        "club": team_names.get(player.team_id, ""),
        "position": POSITION_SHORT.get(player.position_id, ""),
        "price": round(player.cost / 10, 1),
        "status": "" if note is None else (note.get("status") or ""),
        "chance_of_playing_next_round": _chance(note),
        "news": "" if note is None else (note.get("news") or ""),
        "minutes": 0 if note is None else int(note.get("minutes") or 0),
        "fixtures": fixtures_by_team.get(player.team_id, []),
        "projected_points": [round(float(points), 2) for points in player.proj[:PLAN_HORIZON]],
    }


def _dossier(
    players: list[PlayerOpt],
    plans: dict[int, SolvedPlan],
    policy: TransferSuggestion,
    notes: list[dict[str, Any]],
    team_names: dict[int, str],
    fixtures_by_team: dict[int, list[dict[str, Any]]],
    *,
    bank: int,
    free_transfers: int,
    absent: set[int],
    roll: SolvedPlan,
) -> dict[str, Any]:
    by_id = {player.id: player for player in players}
    noted = {}
    for note in notes:
        try:
            noted[int(note["id"])] = note
        except (KeyError, TypeError, ValueError):
            continue
    legal = _candidate_plans(plans, free_transfers)
    alternatives = []
    target_ids: set[int] = set()
    for count in sorted(legal):
        plan = legal[count]
        if not _allowed(plan, policy, roll, free_transfers, absent):
            continue
        for move in plan.moves:
            target_ids.add(move.in_id)
        alternatives.append(
            {
                "transfers": count,
                "moves": [
                    {
                        "out_id": move.out_id,
                        "in_id": move.in_id,
                        "out_name": move.out_name,
                        "in_name": move.in_name,
                    }
                    for move in plan.moves
                ],
                "gain_vs_roll": round(plan.objective - roll.objective, 2),
                "recommended": _pairs(plan) == _policy_pairs(policy) and count == len(policy.moves),
            }
        )
    squad = [
        _brief(by_id[player_id], team_names, fixtures_by_team, noted.get(player_id))
        for player_id in sorted(noted)
        if player_id in by_id
    ]
    targets = [
        _brief(by_id[player_id], team_names, fixtures_by_team, None)
        for player_id in sorted(target_ids)
        if player_id in by_id
    ]
    return {
        "free_transfers": free_transfers,
        "bank": round(bank / 10, 1),
        "squad": squad,
        "targets": targets,
        "alternatives": alternatives,
    }


def _option_pairs(moves: list[Any]) -> list[tuple[int, int]] | None:
    pairs: list[tuple[int, int]] = []
    for move in moves:
        if not isinstance(move, dict):
            return None
        try:
            pairs.append((int(move["out_id"]), int(move["in_id"])))
        except (KeyError, TypeError, ValueError):
            return None
    return pairs


def _options_ok(payload: dict[str, Any], squad_ids: set[int], action: str, moves: list[Any]) -> bool:
    options = payload.get("options")
    if not isinstance(options, list) or not options:
        return False
    top_pairs = _option_pairs(moves)
    if top_pairs is None:
        return False
    pcts: list[int] = []
    chosen = 0
    for option in options:
        if not isinstance(option, dict) or option.get("action") not in {"roll", "transfer"}:
            return False
        reason = option.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return False
        try:
            pct = int(option["recommended_pct"])
        except (KeyError, TypeError, ValueError):
            return False
        if pct < 0 or pct > 100:
            return False
        pcts.append(pct)
        option_moves = option.get("moves")
        incomings = option.get("incomings")
        if not isinstance(option_moves, list) or not isinstance(incomings, list):
            return False
        pairs = _option_pairs(option_moves)
        if pairs is None or len(pairs) != len(set(pairs)):
            return False
        incoming_ids: list[int] = []
        for player in incomings:
            if not isinstance(player, dict):
                return False
            try:
                incoming_ids.append(int(player["element"]))
            except (KeyError, TypeError, ValueError):
                return False
        if incoming_ids != [pair[1] for pair in pairs]:
            return False
        if option.get("chosen") is True:
            chosen += 1
            if option.get("action") != action or pairs != top_pairs:
                return False
        if option.get("action") != "transfer":
            continue
        starters = option.get("starters")
        bench = option.get("bench")
        if not isinstance(starters, list) or not isinstance(bench, list):
            return False
        try:
            placed = [int(player_id) for player_id in [*starters, *bench]]
        except (TypeError, ValueError):
            return False
        placed_ids = set(placed)
        outs = {pair[0] for pair in pairs}
        ins = {pair[1] for pair in pairs}
        if len(placed) != 15 or len(placed_ids) != 15 or outs & placed_ids:
            return False
        if not ins <= placed_ids or not (squad_ids - outs) <= placed_ids:
            return False
    return chosen == 1 and sum(pcts) == 100


def stored_advice_ok(payload: dict[str, Any], squad_ids: set[int], free_transfers: int) -> bool:
    """A cached plan is usable only when it still fits this squad and transfer count."""
    if payload.get("source") not in {"llm", "policy"}:
        return False
    action = payload.get("action")
    moves = payload.get("moves")
    summary = payload.get("summary")
    if action not in {"roll", "transfer"} or not isinstance(moves, list):
        return False
    if not isinstance(summary, str) or not summary.strip():
        return False
    try:
        reported = int(payload.get("free_transfers"))
    except (TypeError, ValueError):
        return False
    if reported != max(0, min(MAX_FREE_TRANSFERS, int(free_transfers))):
        return False
    if not _options_ok(payload, squad_ids, action, moves):
        return False
    incomings = payload.get("incomings")
    if action == "roll":
        return moves == [] and incomings == []

    if not moves or len(moves) > reported or not isinstance(incomings, list):
        return False
    outs: list[int] = []
    ins: list[int] = []
    for move in moves:
        if not isinstance(move, dict):
            return False
        try:
            out_id = int(move["out_id"])
            in_id = int(move["in_id"])
        except (KeyError, TypeError, ValueError):
            return False
        if out_id not in squad_ids or in_id in squad_ids:
            return False
        outs.append(out_id)
        ins.append(in_id)
    if len(set(outs)) != len(outs) or len(set(ins)) != len(ins):
        return False
    incoming_ids: list[int] = []
    for player in incomings:
        if not isinstance(player, dict):
            return False
        try:
            incoming_ids.append(int(player["element"]))
        except (KeyError, TypeError, ValueError):
            return False
    if incoming_ids != ins:
        return False
    starters = payload.get("starters")
    bench = payload.get("bench")
    if not isinstance(starters, list) or not isinstance(bench, list):
        return False
    try:
        placed = [int(player_id) for player_id in [*starters, *bench]]
    except (TypeError, ValueError):
        return False
    placed_ids = set(placed)
    if len(placed) != 15 or len(placed_ids) != 15 or set(outs) & placed_ids:
        return False
    kept = squad_ids - set(outs)
    return kept <= placed_ids and set(ins) <= placed_ids


def _accept(
    payload: dict[str, Any],
    plans: dict[int, SolvedPlan],
    *,
    policy: TransferSuggestion,
    free_transfers: int,
    unavailable_ids: set[int],
    names: dict[int, str],
) -> TransferSuggestion:
    return advice_from_model(
        payload,
        plans,
        policy=policy,
        free_transfers=free_transfers,
        unavailable_ids=unavailable_ids,
        names=names,
    )


async def choose_transfers(
    players: list[PlayerOpt],
    *,
    bank: int,
    free_transfers: int,
    squad_notes: list[dict[str, Any]],
    team_names: dict[int, str],
    fixtures_by_team: dict[int, list[dict[str, Any]]],
    settings: Settings,
    allow_llm: bool,
    client: OpenRouterClient | None = None,
) -> TransferSuggestion:
    """Ask the model whether the best legal moves are clear, else apply the rules."""
    available = max(0, min(MAX_FREE_TRANSFERS, int(free_transfers)))
    solved = optimise_horizon(
        players,
        bank=bank,
        free_transfers=available,
        horizon=PLAN_HORIZON,
        max_hits=0,
    )
    plans: dict[int, SolvedPlan] = solved["all"]
    names = {player.id: player.web_name for player in players}
    roll = plans.get(0)
    if roll is None:
        raise RuntimeError("Unable to solve the roll (0-transfer) plan")
    absent = unavailable_starter_ids(squad_notes, roll.xi_ids)
    policy = advice_from_plans(
        plans,
        free_transfers=available,
        unavailable_ids=absent,
        names=names,
    )
    if not allow_llm or not settings.llm_api_key or not settings.llm_model:
        return policy

    dossier = _dossier(
        players,
        plans,
        policy,
        squad_notes,
        team_names,
        fixtures_by_team,
        bank=bank,
        free_transfers=available,
        absent=absent,
        roll=roll,
    )
    llm = client or OpenRouterClient(settings)
    close_client = client is None
    try:
        return await _from_model(
            llm,
            plans,
            policy,
            dossier,
            free_transfers=available,
            unavailable_ids=absent,
            names=names,
        )
    finally:
        if close_client:
            await llm.aclose()


async def _from_model(
    client: OpenRouterClient,
    plans: dict[int, SolvedPlan],
    policy: TransferSuggestion,
    dossier: dict[str, Any],
    *,
    free_transfers: int,
    unavailable_ids: set[int],
    names: dict[int, str],
) -> TransferSuggestion:
    user = json.dumps(dossier, default=str)
    try:
        raw = await client.chat_with_search(system=TRANSFER_SYSTEM, user=user)
    except LlmError:
        return policy
    try:
        return _accept(
            raw,
            plans,
            policy=policy,
            free_transfers=free_transfers,
            unavailable_ids=unavailable_ids,
            names=names,
        )
    except TransferRejected as exc:
        repair = json.dumps(
            {
                "alternatives": dossier.get("alternatives"),
                "free_transfers": free_transfers,
                "rejected": raw,
                "errors": exc.reasons,
                "instruction": "Return corrected JSON using only an alternative from this payload, or roll. Do not search.",
            },
            default=str,
        )
    try:
        fixed = await client.chat_json(system=TRANSFER_SYSTEM, user=repair)
    except LlmError:
        return policy
    try:
        return _accept(
            fixed,
            plans,
            policy=policy,
            free_transfers=free_transfers,
            unavailable_ids=unavailable_ids,
            names=names,
        )
    except TransferRejected:
        return policy
