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

    async def chat_json(self, *, system: str, user: str) -> dict[str, Any]:
        if not self.settings.llm_api_key:
            raise LlmError("missing LLM API key")
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "HTTP-Referer": self.settings.next_public_site_url,
            "X-Title": "FPLBud",
        }
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        try:
            response = await self._client.post("chat/completions", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise LlmError("timeout") from exc
        except httpx.HTTPError as exc:
            raise LlmError(str(exc)) from exc
        if response.status_code >= 400:
            raise LlmError(f"http {response.status_code}")
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
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
