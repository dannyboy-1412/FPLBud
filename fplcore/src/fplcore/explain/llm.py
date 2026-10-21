from __future__ import annotations

import json

from fplcore.explain.protocol import HorizonResult
from fplcore.explain.template import TemplateExplainer
from fplcore.llm import LlmError, OpenRouterClient, grounding_ok
from fplcore.settings import Settings, get_settings

SYSTEM = (
    "You write a short matchday-programme style paragraph for an FPL team agent. "
    "Use only the names and numbers in the JSON. Do not invent players, prices or points. "
    "Return JSON of the form {\"1\": \"...\", \"3\": \"...\", \"5\": \"...\"}."
)


class LLMExplainer:
    source = "llm"

    def __init__(
        self,
        settings: Settings | None = None,
        client: OpenRouterClient | None = None,
        fallback: TemplateExplainer | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client
        self.fallback = fallback or TemplateExplainer()

    def explain(self, result: HorizonResult) -> str:
        return self.fallback.explain(result)

    def explain_run(self, results: dict[str, HorizonResult]) -> dict[str, str]:
        return self.fallback.explain_run(results)

    async def explain_run_async(self, results: dict[str, HorizonResult]) -> tuple[dict[str, str], str]:
        template = self.fallback.explain_run(results)
        if not self.settings.llm_enabled:
            return template, "template"
        client = self.client or OpenRouterClient(self.settings)
        owns = self.client is None
        payload = json.dumps(results, default=str)
        try:
            parsed = await client.chat_json(system=SYSTEM, user=payload)
            out: dict[str, str] = {}
            for key in results:
                text = parsed.get(str(key)) or parsed.get(key)
                if not isinstance(text, str) or not grounding_ok(text, payload):
                    return template, "template"
                out[str(key)] = text
            if set(out) != set(str(k) for k in results):
                return template, "template"
            return out, "llm"
        except (LlmError, KeyError, TypeError):
            return template, "template"
        finally:
            if owns:
                await client.aclose()
