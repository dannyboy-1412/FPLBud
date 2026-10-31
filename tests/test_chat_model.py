from __future__ import annotations

import json

import httpx

from fplcore.chat.model import LlmError, OpenAICompatClient
from fplcore.chat.types import Message


def _sse(chunks: list[dict]) -> bytes:
    lines = []
    for chunk in chunks:
        lines.append("data: " + json.dumps(chunk))
    lines.append("data: [DONE]")
    lines.append("")
    return ("\n".join(lines) + "\n").encode()


def _client(handler, *, fallback: str = "") -> OpenAICompatClient:  # type: ignore[no-untyped-def]
    return OpenAICompatClient(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        model="primary",
        fallback_model=fallback,
        timeout=5,
        transport=httpx.MockTransport(handler),
        sleeper=_no_sleep,
    )


async def _no_sleep(seconds: float) -> None:
    del seconds


async def test_streams_text_and_reads_usage_from_the_last_chunk() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["tools"][0]["function"]["name"] == "get_my_team"
        return httpx.Response(
            200,
            content=_sse(
                [
                    {"choices": [{"delta": {"content": "Captain "}, "finish_reason": None}]},
                    {"choices": [{"delta": {"content": "Haaland"}, "finish_reason": "stop"}]},
                    {
                        "choices": [],
                        "usage": {
                            "prompt_tokens": 30,
                            "completion_tokens": 4,
                            "cost": 0.001,
                            "prompt_tokens_details": {"cached_tokens": 12},
                        },
                    },
                ]
            ),
        )

    client = _client(handler)
    parts: list[str] = []
    turn = await client.stream(
        [Message(role="user", content="captain?")],
        tools=[{"type": "function", "function": {"name": "get_my_team", "parameters": {}}}],
        max_tokens=100,
        on_text=parts.append,
    )
    assert "".join(parts) == "Captain Haaland"
    assert turn.text == "Captain Haaland"
    assert turn.usage.input_tokens == 30
    assert turn.usage.cached_tokens == 12
    assert turn.usage.cost_usd == 0.001
    assert turn.finish_reason == "stop"
    await client.aclose()
    assert seen == {}


async def test_assembles_tool_call_deltas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse(
                [
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_1",
                                            "function": {"name": "get_player", "arguments": ""},
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"player_id":'}}]},
                                "finish_reason": None,
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "delta": {"tool_calls": [{"index": 0, "function": {"arguments": " 12}"}}]},
                                "finish_reason": "tool_calls",
                            }
                        ]
                    },
                ]
            ),
        )

    client = _client(handler)
    turn = await client.stream([Message(role="user", content="who?")], tools=[{}], max_tokens=50)
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].name == "get_player"
    assert turn.tool_calls[0].arguments == {"player_id": 12}
    assert turn.finish_reason == "tool_calls"
    await client.aclose()


async def test_retries_then_uses_fallback_model() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["model"])
        if body["model"] == "primary":
            return httpx.Response(503, json={"error": "down"})
        return httpx.Response(
            200,
            content=_sse([{"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}]),
        )

    client = _client(handler, fallback="backup")
    turn = await client.stream([Message(role="user", content="hi")], tools=None, max_tokens=20)
    assert calls == ["primary", "primary", "backup"]
    assert turn.model == "backup"
    assert turn.text == "ok"
    await client.aclose()


async def test_does_not_retry_after_text_was_emitted() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n' b"data: not-json\n",
        )

    client = _client(handler, fallback="backup")
    try:
        await client.stream([Message(role="user", content="hi")], tools=None, max_tokens=20)
    except LlmError as exc:
        assert exc.emitted is True
    else:
        raise AssertionError("expected LlmError")
    assert calls["n"] == 1
    await client.aclose()


async def test_missing_key_is_not_retried() -> None:
    client = OpenAICompatClient(api_key="", base_url="https://example.test/v1", model="m", timeout=2)
    try:
        await client.stream([Message(role="user", content="hi")], tools=None, max_tokens=10)
    except LlmError as exc:
        assert "key" in str(exc)
    else:
        raise AssertionError("expected LlmError")
    await client.aclose()
