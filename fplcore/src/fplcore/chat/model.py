from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx

from fplcore.chat.types import FinishReason, ModelTurn, ToolCall, Usage

logger = logging.getLogger("fplbud.chat")

OnText = Callable[[str], None]
Sleeper = Callable[[float], Awaitable[None]]


class LlmError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
        emitted: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.emitted = emitted


class LlmClient(Protocol):
    async def stream(
        self,
        messages: list[Any],
        *,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float = 0.2,
        on_text: OnText | None = None,
    ) -> ModelTurn: ...


def _headers(api_key: str, site_url: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": site_url,
        "X-Title": "FPLBud",
    }


def _usage(raw: dict[str, Any] | None) -> Usage:
    if not raw:
        return Usage()
    details = raw.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens", raw.get("cached_tokens", 0)) or 0
    cost = raw.get("cost")
    return Usage(
        input_tokens=int(raw.get("prompt_tokens") or raw.get("input_tokens") or 0),
        output_tokens=int(raw.get("completion_tokens") or raw.get("output_tokens") or 0),
        cached_tokens=int(cached),
        cost_usd=float(cost) if cost is not None else None,
    )


def _finish(raw: str | None, *, has_tools: bool) -> FinishReason:
    if raw in {"stop", "tool_calls", "length", "content_filter"}:
        return raw  # type: ignore[return-value]
    if raw == "error":
        return "error"
    if has_tools:
        return "tool_calls"
    return "stop"


def _parse_calls(slots: dict[int, dict[str, str]]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for index in sorted(slots):
        slot = slots[index]
        raw = slot.get("arguments") or ""
        name = slot.get("name") or ""
        call_id = slot.get("id") or f"call_{index}"
        if not raw:
            calls.append(ToolCall(id=call_id, name=name, arguments={}, raw_arguments=raw))
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            calls.append(
                ToolCall(id=call_id, name=name, arguments=None, raw_arguments=raw, parse_error=str(exc))
            )
            continue
        if not isinstance(parsed, dict):
            calls.append(
                ToolCall(
                    id=call_id,
                    name=name,
                    arguments=None,
                    raw_arguments=raw,
                    parse_error="arguments were not an object",
                )
            )
            continue
        calls.append(ToolCall(id=call_id, name=name, arguments=parsed, raw_arguments=raw))
    return calls


class OpenAICompatClient:
    """Streaming tool-calling client for any OpenAI-compatible chat endpoint.

    Retries a failed call only before the first text or tool-call delta. A second
    failure uses the fallback model once. Authorization headers are never logged.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        fallback_model: str = "",
        timeout: float = 60.0,
        site_url: str = "http://localhost:3000",
        transport: httpx.AsyncBaseTransport | None = None,
        sleeper: Sleeper | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.site_url = site_url
        self._sleeper = sleeper
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def stream(
        self,
        messages: list[Any],
        *,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float = 0.2,
        on_text: OnText | None = None,
    ) -> ModelTurn:
        if not self.api_key:
            raise LlmError("missing LLM API key")
        if not self.model:
            raise LlmError("missing LLM model")
        try:
            return await self._once(
                self.model, messages, tools=tools, max_tokens=max_tokens, temperature=temperature, on_text=on_text
            )
        except LlmError as first:
            if first.emitted or not first.retryable:
                raise
            await self._sleep(_retry_delay(first))
            try:
                return await self._once(
                    self.model,
                    messages,
                    tools=tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    on_text=on_text,
                )
            except LlmError as second:
                if second.emitted or not self.fallback_model or self.fallback_model == self.model:
                    raise
                logger.warning("chat primary model failed with http %s; trying fallback", second.status)
                return await self._once(
                    self.fallback_model,
                    messages,
                    tools=tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    on_text=on_text,
                )

    async def _sleep(self, seconds: float) -> None:
        if self._sleeper is not None:
            await self._sleeper(seconds)
            return
        import asyncio

        await asyncio.sleep(seconds)

    async def _once(
        self,
        model: str,
        messages: list[Any],
        *,
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
        on_text: OnText | None,
    ) -> ModelTurn:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.to_api() if hasattr(message, "to_api") else message for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = tools
        emitted = False
        try:
            async with self._client.stream(
                "POST",
                "chat/completions",
                json=payload,
                headers=_headers(self.api_key, self.site_url),
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    retryable = response.status_code == 429 or response.status_code >= 500
                    raise LlmError(
                        f"http {response.status_code}: {_error_detail(body)}",
                        status=response.status_code,
                        retryable=retryable,
                    )
                text_parts: list[str] = []
                slots: dict[int, dict[str, str]] = {}
                finish: str | None = None
                usage = Usage()
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise LlmError("garbled stream", retryable=not emitted, emitted=emitted) from exc
                    if chunk.get("usage"):
                        usage = _usage(chunk["usage"])
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    if choice.get("finish_reason"):
                        finish = str(choice["finish_reason"])
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        emitted = True
                        text_parts.append(content)
                        if on_text is not None:
                            on_text(content)
                    for tool_delta in delta.get("tool_calls") or []:
                        emitted = True
                        index = int(tool_delta.get("index") or 0)
                        slot = slots.setdefault(index, {"id": "", "name": "", "arguments": ""})
                        if tool_delta.get("id"):
                            slot["id"] += str(tool_delta["id"])
                        function = tool_delta.get("function") or {}
                        if function.get("name"):
                            slot["name"] += str(function["name"])
                        if function.get("arguments"):
                            slot["arguments"] += str(function["arguments"])
        except LlmError:
            raise
        except httpx.TimeoutException as exc:
            raise LlmError("timeout", retryable=not emitted, emitted=emitted) from exc
        except httpx.HTTPError as exc:
            raise LlmError("connection failed", retryable=not emitted, emitted=emitted) from exc
        calls = _parse_calls(slots)
        text = "".join(text_parts)
        if not text and not calls:
            raise LlmError("empty completion", retryable=not emitted, emitted=emitted)
        return ModelTurn(
            text=text,
            tool_calls=calls,
            finish_reason=_finish(finish, has_tools=bool(calls)),
            usage=usage,
            model=model,
        )


def _retry_delay(error: LlmError) -> float:
    if error.status == 429:
        return 1.0
    return 0.5


def _error_detail(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict) and err.get("message"):
            text = str(err["message"])
        elif isinstance(err, str):
            text = err
    text = " ".join(text.split())
    if len(text) > 180:
        text = text[:177] + "..."
    return text or "no error body"
