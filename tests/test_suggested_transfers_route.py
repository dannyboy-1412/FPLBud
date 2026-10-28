from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.auth import current_user
from api.deps import db_conn
from api.limiter import limiter
from api.routers import me


def _conn() -> Iterator[object]:
    yield object()


def _app() -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(me.router)
    app.dependency_overrides[db_conn] = _conn
    return app


def test_suggested_transfers_requires_sign_in() -> None:
    response = TestClient(_app()).post("/me/suggested-transfers")
    assert response.status_code == 401


def test_suggested_transfers_returns_a_roll(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    app.dependency_overrides[current_user] = lambda: {"id": "user-1"}

    async def fake_build(conn: object, settings: object, user_id: object) -> dict:
        assert user_id == "user-1"
        return {
            "action": "roll",
            "free_transfers": 2,
            "moves": [],
            "starters": [],
            "bench": [],
            "captain_id": None,
            "vice_id": None,
            "incomings": [],
            "summary": "Roll both free transfers. No move is a clear upgrade.",
            "source": "policy",
        }

    monkeypatch.setattr(me, "build_suggested_transfers", fake_build)
    response = TestClient(app).post(
        "/me/suggested-transfers",
        headers={"Authorization": "Bearer " + ("t" * 40)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "roll"
    assert body["free_transfers"] == 2
    assert body["moves"] == []
    assert body["source"] == "policy"
