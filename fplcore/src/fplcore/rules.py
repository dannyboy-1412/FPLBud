"""Transfer legality. The optimiser must only return moves this accepts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SquadSlot:
    player_id: int
    position_id: int
    team_id: int
    sell: int


@dataclass(frozen=True)
class IncomingPlayer:
    player_id: int
    position_id: int
    team_id: int
    now_cost: int
    can_transact: bool


@dataclass(frozen=True)
class TransferVerdict:
    legal: bool
    code: str | None = None
    message: str = ""


def check_transfer(
    squad: list[SquadSlot],
    outgoing_id: int,
    incoming: IncomingPlayer,
    *,
    bank: int,
    team_limit: int = 3,
) -> TransferVerdict:
    """Position, selling-price budget, 3-per-club, already owned, and can_transact."""
    owned = {slot.player_id: slot for slot in squad}
    outgoing = owned.get(outgoing_id)
    if outgoing is None:
        return TransferVerdict(False, "NOT_OWNED", "That player is not in the squad.")
    if incoming.player_id in owned:
        return TransferVerdict(False, "ALREADY_OWNED", "You already own that player.")
    if incoming.position_id != outgoing.position_id:
        return TransferVerdict(False, "POSITION", "The replacement has to play the same position.")
    if not incoming.can_transact:
        return TransferVerdict(False, "CANNOT_TRANSACT", "That player cannot be transferred in.")
    if bank + outgoing.sell - incoming.now_cost < 0:
        return TransferVerdict(False, "BUDGET", "That costs more than the selling price plus the bank.")
    clubs: dict[int, int] = {}
    for slot in squad:
        if slot.player_id == outgoing_id:
            continue
        clubs[slot.team_id] = clubs.get(slot.team_id, 0) + 1
    if clubs.get(incoming.team_id, 0) >= team_limit:
        return TransferVerdict(False, "CLUB_LIMIT", f"A squad can only have {team_limit} players from one club.")
    return TransferVerdict(True, None, "Legal.")
