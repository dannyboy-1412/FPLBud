import json
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest
import respx

from fplcore.chat import titles
from fplcore.settings import Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "llm_provider": "openrouter",
        "llm_api_key": "secret",
        "llm_model": "fallback/model",
        "llm_title_model": "cheap/model",
        "llm_base_url": "https://openrouter.ai/api/v1",
        "llm_timeout_seconds": 2,
        "llm_daily_call_cap": 200,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@contextmanager
def _conn() -> Iterator[object]:
    yield object()


def test_sanitise_title_strips_quotes_and_rejects_a_ramble() -> None:
    assert (
        titles.sanitise_title('  "Haaland vs Salah Captaincy." \n') == "Haaland vs Salah Captaincy"
    )
    assert titles.sanitise_title("") is None
    assert titles.sanitise_title("x" * 61) is None
    assert titles.sanitise_title("line\nwith a break") == "line with a break"


def test_title_source_collapses_whitespace_and_caps_length() -> None:
    assert titles.title_source("  captain \n haaland  ") == "captain haaland"
    assert len(titles.title_source("a" * 800)) == 500


@pytest.mark.asyncio
@respx.mock
async def test_request_title_sends_the_message_as_data() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Haaland vs Salah Captaincy"}}]}
        )

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=handler)
    question = "should i captain haaland or salah this week given fixtures?"
    title = await titles.request_title(_settings(), question)
    body = seen["body"]
    assert isinstance(body, dict)
    assert title == "Haaland vs Salah Captaincy"
    assert body["model"] == "cheap/model"
    assert body["max_tokens"] == 20
    assert body["temperature"] == 0.3
    assert body["reasoning"] == {"effort": "none"}
    assert question not in body["messages"][0]["content"]
    assert body["messages"][1] == {"role": "user", "content": question}
    assert seen["auth"] == "Bearer secret"


@pytest.mark.asyncio
@respx.mock
async def test_request_title_retries_without_reasoning_when_the_model_rejects_it() -> None:
    seen: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        has_reasoning = "reasoning" in body
        seen.append(has_reasoning)
        if has_reasoning:
            return httpx.Response(400, json={"error": {"message": "unknown field"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "Haaland Captaincy"}}]})

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=handler)
    assert await titles.request_title(_settings(), "captain haaland?") == "Haaland Captaincy"
    assert seen == [True, False]


@pytest.mark.asyncio
@respx.mock
async def test_request_title_falls_back_on_http_error() -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(503)
    )
    assert await titles.request_title(_settings(), "captain?") is None


@pytest.mark.asyncio
@respx.mock
async def test_request_title_falls_back_on_timeout() -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("t")
    )
    assert await titles.request_title(_settings(), "captain?") is None


@pytest.mark.asyncio
async def test_disabled_or_capped_title_is_not_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def boom(*_args: object, **_kwargs: object) -> str:
        calls.append("request")
        return "Should Not Run"

    monkeypatch.setattr(titles, "request_title", boom)
    monkeypatch.setattr(titles.chat_repo, "try_title_cap", lambda *_a, **_k: True)
    saved: list[str] = []
    monkeypatch.setattr(titles.chat_repo, "claim_thread_title", lambda *_a, **_k: True)
    monkeypatch.setattr(
        titles.chat_repo, "set_generated_title", lambda *_a, **_k: saved.append("saved")
    )

    await titles.write_thread_title(_conn, _settings(llm_api_key=""), "thread", "user", "captain?")
    await titles.write_thread_title(
        _conn, _settings(llm_provider="other"), "thread", "user", "captain?"
    )

    def no_cap(*_args: object, **_kwargs: object) -> bool:
        calls.append("cap")
        return False

    monkeypatch.setattr(titles.chat_repo, "try_title_cap", no_cap)
    await titles.write_thread_title(_conn, _settings(), "thread", "user", "captain?")
    assert calls == ["cap"]
    assert saved == []


@pytest.mark.asyncio
@respx.mock
async def test_write_thread_title_stores_one_short_title(monkeypatch: pytest.MonkeyPatch) -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": '"Haaland vs Salah Captaincy."'}}]}
        )
    )
    claimed: list[str] = []
    saved: list[str] = []

    def claim(_conn: object, thread_id: str, user_id: str, source: str) -> bool:
        claimed.append(f"{thread_id}:{user_id}:{source}")
        return True

    def store(_conn: object, thread_id: str, user_id: str, title: str) -> None:
        saved.append(f"{thread_id}:{user_id}:{title}")

    monkeypatch.setattr(titles.chat_repo, "claim_thread_title", claim)
    monkeypatch.setattr(titles.chat_repo, "set_generated_title", store)
    monkeypatch.setattr(titles.chat_repo, "try_title_cap", lambda *_a, **_k: True)

    def shared_cap(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("a title must not spend the shared model cap")

    monkeypatch.setattr("fplcore.agent.runner.try_llm_cap", shared_cap)
    await titles.write_thread_title(
        _conn,
        _settings(),
        "thread-1",
        "user-1",
        "should i captain haaland or salah this week given fixtures?",
    )
    assert claimed == [
        "thread-1:user-1:should i captain haaland or salah this week given fixtures?"
    ]
    assert saved == ["thread-1:user-1:Haaland vs Salah Captaincy"]


@pytest.mark.asyncio
async def test_a_lost_claim_does_not_call_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def request(*_args: object, **_kwargs: object) -> str:
        nonlocal called
        called = True
        return "Haaland vs Salah Captaincy"

    monkeypatch.setattr(titles, "request_title", request)
    monkeypatch.setattr(titles.chat_repo, "claim_thread_title", lambda *_a, **_k: False)
    await titles.write_thread_title(_conn, _settings(), "thread", "user", "captain?")
    assert called is False
