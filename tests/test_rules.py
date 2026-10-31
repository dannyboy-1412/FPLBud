from fplcore.rules import IncomingPlayer, SquadSlot, check_transfer


def _squad() -> list[SquadSlot]:
    return [
        SquadSlot(1, 4, 1, 140),
        SquadSlot(2, 4, 1, 70),
        SquadSlot(3, 4, 1, 60),
        SquadSlot(4, 3, 2, 80),
    ]


def _in(**overrides: object) -> IncomingPlayer:
    values: dict[str, object] = {
        "player_id": 9,
        "position_id": 4,
        "team_id": 5,
        "now_cost": 75,
        "can_transact": True,
    }
    values.update(overrides)
    return IncomingPlayer(
        player_id=int(values["player_id"]),  # type: ignore[arg-type]
        position_id=int(values["position_id"]),  # type: ignore[arg-type]
        team_id=int(values["team_id"]),  # type: ignore[arg-type]
        now_cost=int(values["now_cost"]),  # type: ignore[arg-type]
        can_transact=bool(values["can_transact"]),
    )


def test_legal_transfer_uses_selling_price() -> None:
    verdict = check_transfer(_squad(), 1, _in(now_cost=145), bank=5)
    assert verdict.legal


def test_budget_uses_sell_not_a_higher_buy_price() -> None:
    verdict = check_transfer(_squad(), 1, _in(now_cost=150), bank=0)
    assert verdict.code == "BUDGET"


def test_position_must_match() -> None:
    verdict = check_transfer(_squad(), 1, _in(position_id=3), bank=50)
    assert verdict.code == "POSITION"


def test_third_player_from_a_club_is_the_limit() -> None:
    verdict = check_transfer(_squad(), 4, _in(position_id=3, team_id=1), bank=50)
    assert verdict.code == "CLUB_LIMIT"


def test_already_owned_and_missing_and_unsellable() -> None:
    assert check_transfer(_squad(), 1, _in(player_id=2), bank=50).code == "ALREADY_OWNED"
    assert check_transfer(_squad(), 99, _in(), bank=50).code == "NOT_OWNED"
    assert check_transfer(_squad(), 1, _in(can_transact=False), bank=50).code == "CANNOT_TRANSACT"
