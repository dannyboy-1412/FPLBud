from __future__ import annotations

import json
import re
from typing import Any

import httpx

from fplcore.settings import Settings, get_settings


class LlmError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.AsyncClient(
            base_url=self.settings.llm_base_url.rstrip("/") + "/",
            timeout=self.settings.llm_timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "HTTP-Referer": self.settings.next_public_site_url,
            "X-Title": "FPLBud",
        }

    def _search_tool(self) -> dict[str, Any]:
        return {
            "type": "openrouter:web_search",
            "parameters": {
                "max_results": 5,
                "max_uses": self.settings.llm_lineup_max_searches,
                "search_context_size": "low",
            },
        }

    async def _complete(self, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        if not self.settings.llm_api_key:
            raise LlmError("missing LLM API key")
        try:
            response = await self._client.post(
                "chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise LlmError("timeout") from exc
        except httpx.HTTPError as exc:
            raise LlmError(str(exc)) from exc
        if response.status_code >= 400:
            raise LlmError(f"http {response.status_code}")
        body = response.json()
        content = body["choices"][0]["message"].get("content")
        return _parse_json_content(content)

    async def chat_json(self, *, system: str, user: str) -> dict[str, Any]:
        return await self._complete(
            {
                "model": self.settings.llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=self.settings.llm_timeout_seconds,
        )

    async def chat_with_search(self, *, system: str, user: str) -> dict[str, Any]:
        """One completion where the model may call OpenRouter web search before answering."""
        if not self.settings.llm_model:
            raise LlmError("missing LLM model")
        return await self._complete(
            {
                "model": self.settings.llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "tools": [self._search_tool()],
                "temperature": 0.2,
            },
            timeout=self.settings.llm_lineup_timeout_seconds,
        )


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or ""))
        return "".join(parts)
    return ""


def _parse_json_content(content: Any) -> dict[str, Any]:
    text = _message_text(content).strip()
    if not text:
        raise LlmError("empty completion")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise LlmError("invalid json") from None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LlmError("invalid json") from exc
    if not isinstance(parsed, dict):
        raise LlmError("json was not an object")
    return parsed


_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def grounding_ok(text: str, source: str) -> bool:
    """Every number in the output must appear in the source payload."""
    allowed = set(_NUMBER.findall(source))
    for number in _NUMBER.findall(text):
        if number not in allowed:
            return False
    return True
