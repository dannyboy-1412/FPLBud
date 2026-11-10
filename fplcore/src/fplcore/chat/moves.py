"""Computed transfer quotes. The model quotes these numbers; it does not subtract them."""

from __future__ import annotations

from dataclasses import dataclass

from fplcore.optimise import HORIZON_SETTINGS, HorizonSettings
from fplcore.rules import IncomingPlayer, SquadSlot, check_transfer


@dataclass(frozen=True)
class MoveInput:
    out_player_id: int
    incoming: IncomingPlayer
    out_name: str
    in_name: str
    out_proj: float
    in_proj: float


@dataclass(frozen=True)
class MoveQuote:
    out_player_id: int
    in_player_id: int
    out_name: str
    in_name: str
    legal: bool
    code: str | None
    message: str
    out_proj: float
    in_proj: float
    delta: float

    def as_dict(self) -> dict[str, object]:
        return {
            "out_player_id": self.out_player_id,
            "in_player_id": self.in_player_id,
            "out_name": self.out_name,
            "in_name": self.in_name,
            "legal": self.legal,
            "code": self.code,
            "message": self.message,
            "out_proj": self.out_proj,
            "in_proj": self.in_proj,
            "delta": self.delta,
        }


@dataclass(frozen=True)
class TransferQuote:
    moves: list[MoveQuote]
    total_delta: float
    free_transfers_used: int
    hits: int
    hit_cost: int
    net_after_hits: float
    bank_after: int
    verdict: str

    def as_dict(self) -> dict[str, object]:
        return {
            "moves": [move.as_dict() for move in self.moves],
            "total_delta": self.total_delta,
            "free_transfers_used": self.free_transfers_used,
            "hits": self.hits,
            "hit_cost": self.hit_cost,
            "net_after_hits": self.net_after_hits,
            "bank_after": self.bank_after,
            "verdict": self.verdict,
        }


@dataclass(frozen=True)
class Candidate:
    player_id: int
    name: str
    team_id: int
    team: str
    position_id: int
    cost: int
    proj: float
    own: float
    status: str
    can_in: bool


@dataclass(frozen=True)
class RankedReplacement:
    candidate: Candidate
    delta: float


@dataclass(frozen=True)
class ReplacementList:
    budget_tenths: int
    ranked: list[RankedReplacement]
    note: str | None
    owned: bool


def quote_transfers(
    squad: list[SquadSlot],
    moves: list[MoveInput],
    *,
    bank: int,
    free_transfers: int,
    horizon: int,
    team_limit: int = 3,
) -> TransferQuote:
    """Apply each move in order. Bank and club counts change only after a legal sale."""
    current = list(squad)
    cash = bank
    quoted: list[MoveQuote] = []
    total = 0.0
    legal_count = 0
    every_move_legal = True
    for move in moves:
        verdict = check_transfer(
            current,
            move.out_player_id,
            move.incoming,
            bank=cash,
            team_limit=team_limit,
        )
        delta = round(move.in_proj - move.out_proj, 2)
        quoted.append(
            MoveQuote(
                out_player_id=move.out_player_id,
                in_player_id=move.incoming.player_id,
                out_name=move.out_name,
                in_name=move.in_name,
                legal=verdict.legal,
                code=verdict.code,
                message=verdict.message,
                out_proj=move.out_proj,
                in_proj=move.in_proj,
                delta=delta,
            )
        )
        if not verdict.legal:
            every_move_legal = False
            continue
        legal_count += 1
        total = round(total + delta, 2)
        cash, current = _apply(current, move, cash)
    free = max(free_transfers, 0)
    hits = max(0, legal_count - free)
    hit_cost = hits * 4
    return TransferQuote(
        moves=quoted,
        total_delta=total,
        free_transfers_used=min(legal_count, free),
        hits=hits,
        hit_cost=hit_cost,
        net_after_hits=round(total - hit_cost, 2),
        bank_after=cash,
        verdict=_verdict(
            every_move_legal=every_move_legal and legal_count == len(moves) and legal_count > 0,
            total_delta=total,
            hits=hits,
            horizon=horizon,
        ),
    )


def rank_replacements(
    outgoing_id: int,
    squad: list[SquadSlot],
    candidates: list[Candidate],
    *,
    out_proj: float,
    bank: int,
    max_price_tenths: int | None,
    limit: int,
    team_limit: int = 3,
) -> ReplacementList:
    """Same position, affordable after the sale, ranked by projected gain."""
    outgoing = next((slot for slot in squad if slot.player_id == outgoing_id), None)
    if outgoing is None:
        return ReplacementList(bank, [], "That player is not in the squad.", False)
    budget = outgoing.sell + bank
    cap = budget if max_price_tenths is None else min(budget, max_price_tenths)
    owned = {slot.player_id for slot in squad}
    clubs: dict[int, int] = {}
    for slot in squad:
        if slot.player_id == outgoing_id:
            continue
        clubs[slot.team_id] = clubs.get(slot.team_id, 0) + 1
    affordable: list[RankedReplacement] = []
    for candidate in candidates:
        if candidate.player_id == outgoing_id or candidate.player_id in owned:
            continue
        if not candidate.can_in or candidate.position_id != outgoing.position_id:
            continue
        if candidate.cost > cap or clubs.get(candidate.team_id, 0) >= team_limit:
            continue
        affordable.append(RankedReplacement(candidate, round(candidate.proj - out_proj, 2)))
    affordable.sort(key=lambda item: item.delta, reverse=True)
    note = f"Fewer than {limit} are affordable." if len(affordable) < limit else None
    return ReplacementList(budget, affordable[:limit], note, True)


def _apply(squad: list[SquadSlot], move: MoveInput, bank: int) -> tuple[int, list[SquadSlot]]:
    outgoing = next(slot for slot in squad if slot.player_id == move.out_player_id)
    cash = bank + outgoing.sell - move.incoming.now_cost
    kept = [slot for slot in squad if slot.player_id != move.out_player_id]
    kept.append(
        SquadSlot(
            player_id=move.incoming.player_id,
            position_id=move.incoming.position_id,
            team_id=move.incoming.team_id,
            sell=move.incoming.now_cost,
        )
    )
    return cash, kept


def _verdict(*, every_move_legal: bool, total_delta: float, hits: int, horizon: int) -> str:
    if not every_move_legal:
        return "not_worth_it"
    if hits == 0:
        if total_delta > 0:
            return "worth_it"
        if total_delta == 0:
            return "marginal"
        return "not_worth_it"
    settings = HORIZON_SETTINGS.get(horizon) or HorizonSettings(
        n=horizon, delta=0.85, hit_margin=1.0, roll_value=1.0, max_hits_default=1
    )
    bar = 4 + settings.hit_margin
    if total_delta >= bar:
        return "worth_it"
    if total_delta >= 4:
        return "marginal"
    return "not_worth_it"
