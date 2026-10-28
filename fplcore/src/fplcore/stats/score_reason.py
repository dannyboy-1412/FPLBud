from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from fplcore.llm import LlmError, OpenRouterClient, grounding_ok
from fplcore.settings import Settings, get_settings
from fplcore.stats.report import SquadScore

SQUAD_SCORE_SYSTEM = (
    "You explain an FPL squad score in one or two short sentences. "
    "The score is out of 10 for this gameweek's starting XI. "
    "The highest projection is counted twice, the way a captain scores. "
    "Use only the names and numbers in the JSON. Do not invent players, injuries, fixtures, or prices. "
    'Return JSON {"reason": "..."}.'
)

_MAX_REASON_LENGTH = 400


def squad_team_hash(squad_players: list[dict[str, Any]]) -> str:
    """Identity of a cached score sentence: who is in the squad, and where they are picked.

    News and projected points are left out. The sentence stays until the squad or the lineup changes.
    """
    slots = [
        (int(player.get("element") or 0), int(player.get("squad_position") or 0))
        for player in squad_players
        if int(player.get("element") or 0)
    ]
    encoded = json.dumps({"slots": sorted(slots)}, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def squad_score_dossier(scored: SquadScore) -> dict[str, Any]:
    return {
        "score": scored.value,
        "basis": scored.reason,
        "starters": [
            {
                "name": starter.name,
                "projection": round(starter.projection, 1),
                "blank": starter.blank,
                "unlikely": starter.unlikely,
                "not_starting": starter.not_starting,
            }
            for starter in scored.starters
            if starter.name
        ],
    }


def _usable_reason(text: str, source: str) -> str | None:
    cleaned = " ".join(text.split())
    if not cleaned or len(cleaned) > _MAX_REASON_LENGTH:
        return None
    if "http" in cleaned.lower():
        return None
    if not grounding_ok(cleaned, source):
        return None
    return cleaned


async def request_squad_score_reason(
    scored: SquadScore,
    *,
    settings: Settings | None = None,
    client: OpenRouterClient | None = None,
) -> str | None:
    """Ask OpenRouter for the sentence. None means the caller should keep the draft."""
    cfg = settings or get_settings()
    if not cfg.llm_api_key or not cfg.llm_model:
        return None
    payload = json.dumps(squad_score_dossier(scored), sort_keys=True)
    owns_client = client is None
    api = client or OpenRouterClient(cfg)
    try:
        parsed = await api.chat_json(system=SQUAD_SCORE_SYSTEM, user=payload)
    except LlmError:
        return None
    finally:
        if owns_client:
            await api.aclose()
    reason = parsed.get("reason")
    if not isinstance(reason, str):
        return None
    return _usable_reason(reason, payload)


async def resolve_squad_score_reason(
    squad_players: list[dict[str, Any]],
    scored: SquadScore,
    *,
    load: Callable[[str], str | None],
    store: Callable[[str, str], None],
    settings: Settings | None = None,
    client: OpenRouterClient | None = None,
) -> str:
    """Return the stored sentence for this squad, or ask OpenRouter once and store it."""
    team_hash = squad_team_hash(squad_players)
    stored = load(team_hash)
    if stored:
        return stored
    written = await request_squad_score_reason(scored, settings=settings, client=client)
    if not written:
        return scored.reason
    store(team_hash, written)
    return written
