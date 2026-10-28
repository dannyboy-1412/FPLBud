import json

import httpx
import pytest

from fplcore.llm import OpenRouterClient
from fplcore.settings import Settings
from fplcore.stats.report import SquadScore, StarterOutlook
from fplcore.stats.score_reason import (
    request_squad_score_reason,
    resolve_squad_score_reason,
    squad_team_hash,
)


def _settings() -> Settings:
    return Settings(
        llm_api_key="test",
        llm_model="test/model",
        llm_base_url="https://openrouter.ai/api/v1",
        llm_timeout_seconds=2,
    )


def _scored() -> SquadScore:
    return SquadScore(
        value=7.4,
        reason="A premium XI this week.",
        starters=(
            StarterOutlook(name="Haaland", projection=6.2),
            StarterOutlook(name="Gordon", projection=0.0, blank=True),
        ),
    )


def _squad(*slots: tuple[int, int], news: str = "") -> list[dict]:
    return [
        {"element": element, "squad_position": position, "news": news}
        for element, position in slots
    ]


def _client(content: str, calls: dict[str, int]) -> OpenRouterClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.loads(request.content)
        assert body["model"] == "test/model"
        assert "squad score" in body["messages"][0]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return OpenRouterClient(_settings(), transport=httpx.MockTransport(handler))


def test_squad_team_hash_ignores_news_and_changes_with_the_lineup() -> None:
    first = _squad((1, 1), (2, 2), news="hamstring")
    same = _squad((2, 2), (1, 1), news="fit")
    moved = _squad((1, 12), (2, 2))
    assert squad_team_hash(first) == squad_team_hash(same)
    assert squad_team_hash(first) != squad_team_hash(moved)


@pytest.mark.asyncio
async def test_openrouter_reason_is_reused_until_the_squad_changes() -> None:
    calls = {"n": 0}
    client = _client(json.dumps({"reason": "Haaland carries this 7.4."}), calls)
    store: dict[str, str] = {}

    def load(team_hash: str) -> str | None:
        return store.get(team_hash)

    def save(team_hash: str, reason: str) -> None:
        store[team_hash] = reason

    squad = _squad((1, 1), (2, 2))
    first = await resolve_squad_score_reason(
        squad, _scored(), load=load, store=save, settings=_settings(), client=client
    )
    second = await resolve_squad_score_reason(
        list(reversed(squad)),
        _scored(),
        load=load,
        store=save,
        settings=_settings(),
        client=client,
    )
    changed = await resolve_squad_score_reason(
        _squad((1, 12), (2, 2)),
        _scored(),
        load=load,
        store=save,
        settings=_settings(),
        client=client,
    )
    assert first == "Haaland carries this 7.4."
    assert second == first
    assert changed == first
    assert calls["n"] == 2
    assert len(store) == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_openrouter_reason_rejects_an_invented_number_and_is_not_stored() -> None:
    calls = {"n": 0}
    client = _client(json.dumps({"reason": "This XI is worth 99.9."}), calls)
    store: dict[str, str] = {}
    scored = _scored()
    reason = await resolve_squad_score_reason(
        _squad((1, 1)),
        scored,
        load=store.get,
        store=store.__setitem__,
        settings=_settings(),
        client=client,
    )
    assert reason == scored.reason
    assert store == {}
    assert calls["n"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_missing_openrouter_key_keeps_the_draft() -> None:
    scored = _scored()
    reason = await request_squad_score_reason(scored, settings=Settings(llm_api_key="", llm_model=""))
    assert reason is None
