"""Accent-folded player names, nicknames, and the MENTIONED line."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

NICKNAMES = {
    "kdb": "de bruyne",
    "trent": "alexander arnold",
    "taa": "alexander arnold",
}

_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "you",
        "your",
        "who",
        "what",
        "when",
        "where",
        "how",
        "should",
        "would",
        "could",
        "captain",
        "team",
        "squad",
        "next",
        "gameweek",
        "worth",
        "over",
        "under",
        "from",
        "with",
        "that",
        "this",
        "have",
        "wildcard",
        "bench",
        "lineup",
        "rate",
        "any",
        "problems",
        "replace",
        "transfer",
        "transfers",
        "chip",
        "chips",
        "hit",
        "hits",
        "points",
        "price",
        "about",
        "does",
        "not",
        "out",
        "his",
        "her",
        "their",
        "into",
        "are",
        "was",
        "can",
        "get",
        "buy",
        "sell",
        "week",
        "weeks",
    }
)


@dataclass(frozen=True)
class NameRecord:
    player_id: int
    web_name: str
    first_name: str
    second_name: str
    team: str
    position: str
    price_m: float


@dataclass(frozen=True)
class Mentioned:
    line: str
    resolved: dict[int, str]


_LETTER = str.maketrans(
    {
        "ø": "o",
        "æ": "ae",
        "å": "a",
        "ł": "l",
        "đ": "d",
        "ß": "ss",
    }
)


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold().translate(_LETTER))
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.replace("-", " ")


def match_query(query: str, players: list[NameRecord]) -> list[NameRecord]:
    """Best players for one typed name. Exact names win; longer fragments may match inside a name."""
    needle = fold(query).strip()
    if len(needle) < 2:
        return []
    needles = [needle]
    alias = NICKNAMES.get(needle)
    if alias:
        needles.append(fold(alias))
    found: list[NameRecord] = []
    seen: set[int] = set()
    for player in players:
        fields = _fields(player)
        if any(_query_hit(item, fields) for item in needles):
            if player.player_id not in seen:
                seen.add(player.player_id)
                found.append(player)
    return found


def mentioned_in(text: str, players: list[NameRecord]) -> Mentioned:
    """Resolved ids and any surname that matches more than one player."""
    phrases = _phrases(text)
    index = _index(players)
    resolved: dict[int, NameRecord] = {}
    order: list[int] = []
    ambiguous: list[tuple[str, list[NameRecord]]] = []
    used: list[str] = []
    for display, phrase in sorted(phrases, key=lambda item: len(item[1]), reverse=True):
        if _covered(phrase, used):
            continue
        hits = _unique(index.get(phrase, []))
        if len(hits) == 1:
            player = hits[0]
            if player.player_id not in resolved:
                resolved[player.player_id] = player
                order.append(player.player_id)
            used.append(phrase)
            continue
        if len(hits) > 1:
            ambiguous.append((display, hits))
            used.append(phrase)
    line = _render([resolved[player_id] for player_id in order], ambiguous)
    return Mentioned(line, {player_id: resolved[player_id].web_name for player_id in order})


def insert_mentioned(context: str, line: str) -> str:
    if not line:
        return context
    if "</context>" in context:
        return context.replace("</context>", f"{line}\n</context>", 1)
    return f"{context}\n{line}"


def _query_hit(needle: str, fields: list[str]) -> bool:
    if any(needle == field for field in fields):
        return True
    return len(needle) >= 4 and any(needle in field for field in fields)


def _fields(player: NameRecord) -> list[str]:
    full = fold(f"{player.first_name} {player.second_name}")
    return [fold(player.web_name), fold(player.second_name), full]


def _index(players: list[NameRecord]) -> dict[str, list[NameRecord]]:
    index: dict[str, list[NameRecord]] = {}
    for player in players:
        for key in _fields(player):
            if len(key) < 3:
                continue
            index.setdefault(key, []).append(player)
    return index


def _phrases(text: str) -> list[tuple[str, str]]:
    raw = _TOKEN.findall(text)
    folded = [fold(token) for token in raw]
    phrases: list[tuple[str, str]] = []
    for size in (1, 2, 3):
        for start in range(0, len(raw) - size + 1):
            display = " ".join(raw[start : start + size])
            phrase = " ".join(folded[start : start + size]).strip()
            if len(phrase) < 3 or phrase in _STOP:
                continue
            phrases.append((display, phrase))
            alias = NICKNAMES.get(phrase)
            if alias:
                phrases.append((display, fold(alias)))
    return phrases


def _covered(phrase: str, used: list[str]) -> bool:
    return any(phrase != previous and phrase in previous for previous in used)


def _unique(players: list[NameRecord]) -> list[NameRecord]:
    seen: set[int] = set()
    unique: list[NameRecord] = []
    for player in players:
        if player.player_id in seen:
            continue
        seen.add(player.player_id)
        unique.append(player)
    return unique


def _render(resolved: list[NameRecord], ambiguous: list[tuple[str, list[NameRecord]]]) -> str:
    parts = [
        f"{player.player_id} {player.web_name} {player.team} {player.position} £{player.price_m:.1f}m"
        for player in resolved
    ]
    for label, group in ambiguous:
        bits = ", ".join(f"{player.player_id} {player.team}" for player in group[:4])
        parts.append(f'AMBIGUOUS "{label}": {bits}')
    if not parts:
        return ""
    return "MENTIONED: " + " | ".join(parts)
