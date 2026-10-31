"""Short rule cards. The model must quote these, not invent the scoring system."""

from __future__ import annotations

RULES_VERSION = "2026-27-a"
LAST_VERIFIED = "2026-10-12"

TOPICS: dict[str, str] = {
    "squad": (
        "A squad is 15 players: 2 goalkeepers, 5 defenders, 5 midfielders and 3 forwards. "
        "The budget is £100.0m. At most 3 players from one club. "
        "You pick 11 starters. A formation needs at least 1 goalkeeper, 3 defenders, 2 midfielders and 1 forward."
    ),
    "transfers": (
        "A free transfer can be saved, up to a maximum of 5. "
        "Each transfer beyond the free ones costs 4 points, taken from the gameweek score. "
        "Selling price can be below the current price after a fall. "
        "Budget uses the selling price of the player going out, not the price you paid."
    ),
    "hits": (
        "A hit is −4 points per extra transfer. "
        "FPLBud only suggests a hit when the projected gain clears that cost with a margin. "
        "The margin is a model setting, not a guarantee."
    ),
    "chips": (
        "Each half of the season (gameweeks 1–19 and 20–38) has its own Wildcard, Free Hit, Bench Boost and Triple Captain. "
        "Wildcard and Free Hit allow unlimited transfers for that week. A Free Hit squad reverts afterwards. "
        "Bench Boost scores your bench. Triple Captain triples the captain. "
        "Chip timing in FPLBud is a heuristic, not a solved plan."
    ),
    "deadlines": (
        "The gameweek deadline is the first kickoff. After it, transfers and chips apply to the next gameweek. "
        "FPLBud will not tell you to make a change for a deadline that has already passed."
    ),
    "prices": (
        "Prices are in tenths of a million internally and shown as £m to one decimal. "
        "Price-rise lists are pressure signals, not confirmed changes."
    ),
}


def explain(topic: str) -> dict[str, str] | None:
    text = TOPICS.get(topic)
    if text is None:
        return None
    return {
        "topic": topic,
        "text": text,
        "rules_version": RULES_VERSION,
        "last_verified": LAST_VERIFIED,
    }
