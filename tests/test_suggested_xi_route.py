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


def test_suggested_xi_requires_sign_in() -> None:
    response = TestClient(_app()).post("/me/suggested-xi")
    assert response.status_code == 401


def test_suggested_xi_returns_lineup(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    app.dependency_overrides[current_user] = lambda: {"id": "user-1"}

    async def fake_build(conn: object, settings: object, user_id: object) -> dict:
        assert user_id == "user-1"
        return {
            "starters": list(range(1, 12)),
            "bench": [12, 13, 14, 15],
            "captain_id": 1,
            "vice_id": 2,
            "summary": "Start the fit defenders.",
            "source": "llm",
        }

    monkeypatch.setattr(me, "build_suggested_xi", fake_build)
    response = TestClient(app).post(
        "/me/suggested-xi",
        headers={"Authorization": "Bearer " + ("t" * 40)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "llm"
    assert body["starters"] == list(range(1, 12))
    assert body["bench"] == [12, 13, 14, 15]
    assert body["captain_id"] == 1
    assert body["vice_id"] == 2
    assert body["summary"] == "Start the fit defenders."
