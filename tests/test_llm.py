import json

import httpx
import pytest
import respx

from fplcore.explain.llm import LLMExplainer
from fplcore.llm import OpenRouterClient, grounding_ok
from fplcore.settings import Settings


def test_grounding_rejects_invented_numbers() -> None:
    source = json.dumps({"gain": 1.2, "name": "Palmer"})
    assert grounding_ok("Palmer at 1.2", source)
    assert not grounding_ok("Palmer at 9.9", source)


@pytest.mark.asyncio
async def test_llm_fallback_on_invented_number() -> None:
    settings = Settings(
        llm_enabled=True,
        llm_api_key="test",
        llm_model="test/model",
        llm_base_url="https://openrouter.ai/api/v1",
        llm_timeout_seconds=2,
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"1": "Buy Ghost for 99.9 points"})
                        }
                    }
                ]
            },
        )
    )
    client = OpenRouterClient(settings, transport=transport)
    explainer = LLMExplainer(settings, client=client)
    results = {
        "1": {
            "horizon": 1,
            "transfers": [],
            "hits": 0,
            "gain_vs_roll": 0,
            "captain": {"web_name": "Haaland", "proj": 8.1},
            "reason_codes": [],
        }
    }
    texts, source = await explainer.explain_run_async(results)
    assert source == "template"
    assert "Roll" in texts["1"] or "roll" in texts["1"].lower() or "Hold" in texts["1"] or "hold" in texts["1"].lower()
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_llm_timeout_falls_back() -> None:
    settings = Settings(
        llm_enabled=True,
        llm_api_key="test",
        llm_model="test/model",
        llm_base_url="https://openrouter.ai/api/v1",
        llm_timeout_seconds=0.01,
    )
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=httpx.TimeoutException("t"))
    client = OpenRouterClient(settings)
    explainer = LLMExplainer(settings, client=client)
    texts, source = await explainer.explain_run_async(
        {"1": {"horizon": 1, "transfers": [], "hits": 0, "gain_vs_roll": 0, "captain": {}, "reason_codes": []}}
    )
    assert source == "template"
    assert texts["1"]
    await client.aclose()
