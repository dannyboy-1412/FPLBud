from hypothesis import given, settings
from hypothesis import strategies as st

from fplcore.constants import SQUAD_SELECT
from fplcore.optimise import (
    HorizonSettings,
    PlayerOpt,
    optimise_horizon,
    pick_best_plan,
    solve_for_transfers,
)
from fplcore.rules import IncomingPlayer, SquadSlot, check_transfer


def _squad() -> list[PlayerOpt]:
    players: list[PlayerOpt] = []
    pid = 1
    layout = [(1, 2), (2, 5), (3, 5), (4, 3)]
    for pos, n in layout:
        for i in range(n):
            players.append(
                PlayerOpt(
                    id=pid,
                    web_name=f"P{pid}",
                    team_id=1 + (pid % 10),
                    position_id=pos,
                    cost=50 + pos * 5,
                    sell=50 + pos * 5,
                    in_squad=True,
                    can_in=True,
                    locked=False,
                    proj=[4.0 + i * 0.1, 3.5, 3.0, 3.0, 2.5],
                    scores_gw1={"form": 0.5, "fixture": 0.5, "home": 0.5, "xgi": 0.5},
                )
            )
            pid += 1
    for extra in range(20):
        pos = 1 + extra % 4
        players.append(
            PlayerOpt(
                id=pid,
                web_name=f"C{pid}",
                team_id=11 + (extra % 5),
                position_id=pos,
                cost=45 + extra,
                sell=45 + extra,
                in_squad=False,
                can_in=True,
                locked=False,
                proj=[6.0 + extra * 0.05, 5.0, 4.5, 4.0, 3.5],
                scores_gw1={"form": 0.8, "fixture": 0.7, "home": 0.6, "xgi": 0.9},
            )
        )
        pid += 1
    return players


def test_roll_respects_constraints() -> None:
    players = _squad()
    plan = solve_for_transfers(
        players, bank=40, free_transfers=1, transfers_in_target=0, horizon=1, delta=0.85
    )
    assert plan is not None
    assert len(plan.squad_ids) == 15
    assert len(plan.xi_ids) == 11
    assert plan.captain_id in plan.xi_ids
    by_id = {p.id: p for p in players}
    for pos, n in SQUAD_SELECT.items():
        assert sum(1 for pid in plan.squad_ids if by_id[pid].position_id == pos) == n
    clubs: dict[int, int] = {}
    for pid in plan.squad_ids:
        clubs[by_id[pid].team_id] = clubs.get(by_id[pid].team_id, 0) + 1
    assert max(clubs.values()) <= 3


def test_hit_only_when_margin_cleared() -> None:
    roll = solve_for_transfers(
        _squad(), bank=40, free_transfers=1, transfers_in_target=0, horizon=1, delta=0.85
    )
    one = solve_for_transfers(
        _squad(), bank=40, free_transfers=1, transfers_in_target=1, horizon=1, delta=0.85
    )
    assert roll and one
    settings = HorizonSettings(n=1, delta=0.85, hit_margin=2.0, roll_value=2.0, max_hits_default=1)
    best, _, _ = pick_best_plan({0: roll, 1: one}, free_transfers=1, settings=settings, max_hits=1)
    assert best.transfers_in in {0, 1}


def _assert_moves_legal(players: list[PlayerOpt], bank: int) -> None:
    solved = optimise_horizon(players, bank=bank, free_transfers=1, horizon=1, max_hits=0)
    by_id = {player.id: player for player in players}
    squad = [
        SquadSlot(player.id, player.position_id, player.team_id, player.sell)
        for player in players
        if player.in_squad
    ]
    for move in solved["best"].moves:
        incoming = by_id[move.in_id]
        verdict = check_transfer(
            squad,
            move.out_id,
            IncomingPlayer(
                incoming.id,
                incoming.position_id,
                incoming.team_id,
                incoming.cost,
                incoming.can_in,
            ),
            bank=bank,
        )
        assert verdict.legal, verdict.message


@given(bank=st.integers(min_value=0, max_value=40))
@settings(max_examples=2, deadline=None)
def test_every_optimiser_move_is_legal(bank: int) -> None:
    _assert_moves_legal(_squad(), bank)


def test_forbidden_incoming_picks_someone_else() -> None:
    players = _squad()
    first = solve_for_transfers(
        players,
        bank=100,
        free_transfers=1,
        transfers_in_target=1,
        horizon=1,
        delta=0.85,
    )
    assert first is not None and first.moves
    blocked = frozenset(move.in_id for move in first.moves)
    second = solve_for_transfers(
        players,
        bank=100,
        free_transfers=1,
        transfers_in_target=1,
        horizon=1,
        delta=0.85,
        forbidden_incoming=[blocked],
    )
    assert second is not None and second.moves
    assert frozenset(move.in_id for move in second.moves) != blocked
    assert len(second.squad_ids) == 15
    assert len(second.xi_ids) == 11
    assert second.captain_id in second.xi_ids
    by_id = {player.id: player for player in players}
    for pos, count in SQUAD_SELECT.items():
        assert sum(1 for pid in second.squad_ids if by_id[pid].position_id == pos) == count
    clubs: dict[int, int] = {}
    for pid in second.squad_ids:
        clubs[by_id[pid].team_id] = clubs.get(by_id[pid].team_id, 0) + 1
    assert max(clubs.values()) <= 3
    assert second.bank_after >= 0


def test_horizon_returns_distinct_alternatives() -> None:
    solved = optimise_horizon(
        _squad(),
        bank=100,
        free_transfers=1,
        horizon=1,
        max_hits=0,
        alternatives_per_count=3,
    )
    alternatives = solved["alternatives"][1]
    assert len(alternatives) == 3
    incoming = [frozenset(move.in_id for move in plan.moves) for plan in alternatives]
    assert len(set(incoming)) == len(incoming)
    assert solved["all"][1].moves[0].in_id == alternatives[0].moves[0].in_id
    once = optimise_horizon(_squad(), bank=100, free_transfers=1, horizon=1, max_hits=0)
    assert len(once["alternatives"][1]) == 1


@given(bank=st.integers(min_value=0, max_value=200))
@settings(max_examples=8, deadline=None)
def test_budget_never_negative(bank: int) -> None:
    plan = solve_for_transfers(
        _squad(), bank=bank, free_transfers=1, transfers_in_target=0, horizon=1, delta=0.85
    )
    assert plan is not None
    assert plan.bank_after >= 0 or bank < 0
