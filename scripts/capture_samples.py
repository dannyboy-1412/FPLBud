"""Fetch live FPL JSON into samples/ for tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1] / "samples"
BASE = "https://fantasy.premierleague.com/api"


async def save(client: httpx.AsyncClient, path: str, name: str) -> None:
    response = await client.get(path)
    (ROOT / name).write_text(json.dumps(response.json() if response.status_code == 200 else {"status": response.status_code, "body": response.text}, indent=2), encoding="utf-8")
    print(name, response.status_code)


async def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=BASE + "/", timeout=60) as client:
        bootstrap = (await client.get("bootstrap-static/")).json()
        (ROOT / "bootstrap-static.json").write_text(json.dumps(bootstrap), encoding="utf-8")
        fixtures = (await client.get("fixtures/")).json()
        (ROOT / "fixtures.json").write_text(json.dumps(fixtures), encoding="utf-8")
        player_id = bootstrap["elements"][0]["id"]
        await save(client, f"element-summary/{player_id}/", "element-summary.json")
        # A well-known public entry used in the architecture notes. Fall back to 1.
        entry_id = 1
        for candidate in (1, 2, 3):
            r = await client.get(f"entry/{candidate}/")
            if r.status_code == 200:
                entry_id = candidate
                (ROOT / "entry.json").write_text(json.dumps(r.json()), encoding="utf-8")
                event = r.json()["current_event"]
                await save(client, f"entry/{entry_id}/event/{event}/picks/", "picks.json")
                await save(client, f"entry/{entry_id}/history/", "history.json")
                await save(client, f"entry/{entry_id}/transfers/", "transfers.json")
                break
        await save(client, "entry/0/", "entry-404.json")
    print("wrote", ROOT)


if __name__ == "__main__":
    asyncio.run(main())
