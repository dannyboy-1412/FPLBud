import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.chat import runtime as runtime_mod
from api.chat.auth_dep import chat_user
from api.chat.runtime import ChatRuntime
from api.chat.sse import frames
from api.limiter import limiter
from api.routers import chat
from fplcore.chat.events import DoneEvent
from fplcore.chat.guard import IdentityFinaliser
from fplcore.chat.model import LlmError
from fplcore.chat.prompt import ContextView
from fplcore.chat.registry import ToolRegistry, null_connection
from fplcore.chat.testing import ScriptedLlm, text_turn
from fplcore.settings import Settings

THREAD = "11111111-1111-1111-1111-111111111111"


class Conn:
    def execute(self, *_args: object, **_kwargs: object) -> "Conn":
        return self

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"chat_enabled": True, "chat_llm_model": "scripted", "chat_max_concurrent_turns": 4}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _parse(body: str) -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        if not block.strip() or block.lstrip().startswith(":"):
            continue
        name = ""
        data = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data += line.split(":", 1)[1].strip()
        if name and data:
            found.append((name, json.loads(data)))
    return found


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    claim: object,
    *,
    llm: object | None = None,
) -> tuple[ChatRuntime, dict[str, int], ScriptedLlm]:
    opens = {"n": 0, "during": -1}

    @contextmanager
    def open_conn() -> Iterator[Conn]:
        opens["n"] += 1
        try:
            yield Conn()
        finally:
            opens["n"] -= 1

    script = llm if llm is not None else ScriptedLlm([text_turn("Roll the transfer.")])

    def on_stream() -> None:
        opens["during"] = opens["n"]

    if isinstance(script, ScriptedLlm):
        script.on_stream = on_stream
    monkeypatch.setattr(runtime_mod.chat_repo, "latest_snapshot", lambda *_a, **_k: {"id": 1})
    monkeypatch.setattr(runtime_mod.chat_repo, "claim_turn", claim)
    monkeypatch.setattr(runtime_mod.chat_repo, "get_thread", lambda *_a, **_k: {"id": THREAD, "context": None})
    monkeypatch.setattr(runtime_mod.chat_repo, "model_messages", lambda *_a, **_k: [])
    monkeypatch.setattr(runtime_mod.chat_repo, "pin_context", lambda *_a, **_k: True)
    monkeypatch.setattr(runtime_mod.chat_repo, "append_messages", lambda *_a, **_k: [1])
    monkeypatch.setattr(runtime_mod.chat_repo, "complete_turn", lambda *_a, **_k: 9)
    monkeypatch.setattr(runtime_mod.chat_repo, "fail_turn", lambda *_a, **_k: None)
    monkeypatch.setattr(runtime_mod.chat_repo, "abandon_turn", lambda *_a, **_k: True)
    monkeypatch.setattr(runtime_mod.chat_repo, "load_turn_trace", lambda *_a, **_k: {"tool_calls": []})
    monkeypatch.setattr(runtime_mod.chat_repo, "global_spend", lambda *_a, **_k: 0.0)
    monkeypatch.setattr(runtime_mod.chat_repo, "record_blocked", lambda *_a, **_k: None)
    monkeypatch.setattr(runtime_mod, "build_context", lambda *_a, **_k: ContextView(decision_gw=10, season_id="2026/27"))
    runtime = ChatRuntime(
        settings=_settings(),
        open_conn=open_conn,
        llm=script,
        tools=ToolRegistry([], open_conn=null_connection),
        finaliser=IdentityFinaliser(),
        canary="canary",
    )
    return runtime, opens, script  # type: ignore[return-value]


def _app(runtime: ChatRuntime, *, signed_in: bool = True) -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(chat.router)
    app.state.chat_runtime = runtime
    if signed_in:
        app.dependency_overrides[chat_user] = lambda: {"id": "user-1"}
    return app


def _auth(tag: str) -> dict[str, str]:
    token = ("a" * 16) + tag
    return {"Authorization": "Bearer " + token}


def _start(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
        "status": "start",
        "turn_id": 4,
        "user_message_id": 8,
        "turns_left": 19,
    }


def test_send_streams_final_and_does_not_hold_a_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, opens, script = _wire(monkeypatch, _start)
    with TestClient(_app(runtime)) as client:
        response = client.post(
            f"/chat/threads/{THREAD}/messages",
            json={"text": "Who should I captain?", "client_msg_id": "m1"},
            headers=_auth("stream-final-aaaa"),
        )
    assert response.status_code == 200
    names = [name for name, _payload in _parse(response.text)]
    assert names[0] == "turn.start"
    assert "message.delta" in names
    assert names[-3:] == ["message.final", "usage", "done"]
    final = next(payload for name, payload in _parse(response.text) if name == "message.final")
    assert final["text"] == "Roll the transfer."
    assert final["grounding"] == "ok"
    assert opens["during"] == 0
    assert opens["n"] == 0
    assert script.seen


def test_replay_does_not_call_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def claim(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "status": "replay",
            "turn_id": 4,
            "message_id": 9,
            "text": "Already answered.",
            "citations": [],
            "grounding": "ok",
            "turns_left": 19,
        }

    runtime, _opens, script = _wire(monkeypatch, claim)
    with TestClient(_app(runtime)) as client:
        response = client.post(
            f"/chat/threads/{THREAD}/messages",
            json={"text": "Who should I captain?", "client_msg_id": "m1"},
            headers=_auth("replay-no-model-aa"),
        )
    assert response.status_code == 200
    names = [name for name, _payload in _parse(response.text)]
    assert names == ["turn.start", "message.final", "usage", "done"]
    assert script.seen == []


def test_provider_error_then_done(monkeypatch: pytest.MonkeyPatch) -> None:
    class Down:
        async def stream(self, *_args: object, **_kwargs: object) -> None:
            raise LlmError("down", status=503, retryable=True)

        on_stream = None

    runtime, _opens, _script = _wire(monkeypatch, _start, llm=Down())
    failed: list[str] = []
    monkeypatch.setattr(runtime_mod.chat_repo, "fail_turn", lambda *_a, **k: failed.append(str(k.get("error_code"))))
    with TestClient(_app(runtime)) as client:
        response = client.post(
            f"/chat/threads/{THREAD}/messages",
            json={"text": "Who should I captain?"},
            headers=_auth("provider-error-aa"),
        )
    names = [name for name, _payload in _parse(response.text)]
    assert names[-2:] == ["error", "done"]
    error = next(payload for name, payload in _parse(response.text) if name == "error")
    assert error["code"] == "UNAVAILABLE"
    assert failed == ["UNAVAILABLE"]


@pytest.mark.parametrize(
    ("status", "code", "http"),
    [
        ("missing", "NOT_FOUND", 404),
        ("busy", "TURN_IN_PROGRESS", 409),
        ("capped", "CAPPED", 429),
    ],
)
def test_claim_refusals(monkeypatch: pytest.MonkeyPatch, status: str, code: str, http: int) -> None:
    def claim(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"status": status, "scope": "user", "turns_left": 0}

    runtime, _opens, _script = _wire(monkeypatch, claim)
    with TestClient(_app(runtime)) as client:
        response = client.post(
            f"/chat/threads/{THREAD}/messages",
            json={"text": "Who should I captain?"},
            headers=_auth(f"refuse-{status}"),
        )
    assert response.status_code == http
    assert response.json()["detail"]["code"] == code


def test_sign_in_required(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, _opens, _script = _wire(monkeypatch, _start)
    with TestClient(_app(runtime, signed_in=False)) as client:
        response = client.post(f"/chat/threads/{THREAD}/messages", json={"text": "Hello"})
    assert response.status_code == 401


def test_chat_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, _opens, _script = _wire(monkeypatch, _start)
    runtime.settings = _settings(chat_enabled=False)
    with TestClient(_app(runtime)) as client:
        response = client.post(
            f"/chat/threads/{THREAD}/messages",
            json={"text": "Hello"},
            headers=_auth("disabled-chat-aaa"),
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "CHAT_DISABLED"


def test_empty_question_is_not_charged(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"claim": 0, "blocked": 0}

    def claim(*_args: object, **_kwargs: object) -> dict[str, object]:
        called["claim"] += 1
        return _start()

    runtime, _opens, _script = _wire(monkeypatch, claim)
    monkeypatch.setattr(
        runtime_mod.chat_repo,
        "record_blocked",
        lambda *_a, **_k: called.__setitem__("blocked", called["blocked"] + 1),
    )
    with TestClient(_app(runtime)) as client:
        response = client.post(
            f"/chat/threads/{THREAD}/messages",
            json={"text": "   "},
            headers=_auth("empty-question-aa"),
        )
    assert response.status_code == 400
    assert called["claim"] == 0
    assert called["blocked"] == 1


def test_cancel_marks_the_turn_abandoned(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, opens, _script = _wire(monkeypatch, _start)
    abandoned = {"n": 0}
    monkeypatch.setattr(runtime_mod.chat_repo, "abandon_turn", lambda *_a, **_k: abandoned.__setitem__("n", 1) or True)
    prepared = asyncio.run(runtime.prepare(user_id="user-1", thread_id=THREAD, text="Who?", client_msg_id=None, client="test"))

    async def cancel() -> None:
        assert not isinstance(prepared, runtime_mod.Refuse)
        agen = runtime.events(prepared)
        await agen.__anext__()
        await agen.aclose()

    asyncio.run(cancel())
    assert abandoned["n"] == 1
    assert opens["n"] == 0


def test_heartbeat_while_quiet() -> None:
    async def events():
        await asyncio.sleep(0.05)
        yield DoneEvent(turn_id=1, status="ok")

    async def collect() -> list[str]:
        return [chunk async for chunk in frames(events(), interval=0.01)]

    chunks = asyncio.run(collect())
    assert any(chunk.startswith(": ping") for chunk in chunks)
    assert any(chunk.startswith("event: done") for chunk in chunks)
