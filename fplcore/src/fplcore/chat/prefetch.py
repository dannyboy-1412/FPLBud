"""One read-only tool, chosen only when the question names a single intent."""

from __future__ import annotations

import re

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("get_captain_options", re.compile(r"\b(captain|captaincy)\b", re.IGNORECASE)),
    ("get_best_lineup", re.compile(r"\b(bench|lineup|line-up)\b", re.IGNORECASE)),
    ("get_plan_suggestions", re.compile(r"\b(wildcard|free hit|chip)\b", re.IGNORECASE)),
    ("review_my_squad", re.compile(r"\b(rate my (team|squad)|any problems)\b", re.IGNORECASE)),
)


def prefetch_tool(text: str) -> str | None:
    """The tool to run before the first model call, or nothing if the intent is mixed."""
    cleaned = re.sub(r"\b(?:bench boost|triple captain)\b", " ", text, flags=re.IGNORECASE)
    found = [name for name, pattern in _RULES if pattern.search(cleaned)]
    if len(found) == 1:
        return found[0]
    return None
