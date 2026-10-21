from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from fplcore.models import (
    BootstrapStatic,
    ElementSummary,
    Entry,
    EntryHistory,
    Fixture,
    PicksPayload,
    TransferRow,
)
from fplcore.settings import Settings, get_settings


class FplNotFoundError(LookupError):
    def __init__(self, path: str) -> None:
        super().__init__(f"FPL resource not found: {path}")
        self.path = path


class TokenBucket:
    def __init__(self, rate: float) -> None:
        self.rate = max(rate, 0.1)
        self._tokens = self.rate
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._updated
            self._tokens = min(self.rate, self._tokens + elapsed * self.rate)
            self._updated = now
            if self._tokens < 1:
                await asyncio.sleep((1 - self._tokens) / self.rate)
                self._tokens = 0
                self._updated = time.monotonic()
            else:
                self._tokens -= 1


class FplClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._bucket = TokenBucket(self.settings.fpl_max_requests_per_second)
        self._client = httpx.AsyncClient(
            base_url=self.settings.fpl_api_base_url + "/",
            timeout=self.settings.fpl_request_timeout_seconds,
            transport=transport,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> FplClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _get(self, path: str, *, retries: int = 3) -> Any:
        delay = 0.5
        last_error: Exception | None = None
        for attempt in range(retries):
            await self._bucket.acquire()
            try:
                response = await self._client.get(path)
            except httpx.HTTPError as exc:
                last_error = exc
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if response.status_code == 404:
                raise FplNotFoundError(path)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            return response.json()
        if last_error:
            raise last_error
        raise RuntimeError(f"FPL request failed: {path}")

    async def bootstrap_static(self) -> BootstrapStatic:
        return BootstrapStatic.model_validate(await self._get("bootstrap-static/"))

    async def fixtures(self) -> list[Fixture]:
        payload = await self._get("fixtures/")
        return [Fixture.model_validate(row) for row in payload]

    async def element_summary(self, player_id: int) -> ElementSummary:
        return ElementSummary.model_validate(await self._get(f"element-summary/{player_id}/"))

    async def entry(self, entry_id: int) -> Entry:
        return Entry.model_validate(await self._get(f"entry/{entry_id}/"))

    async def entry_picks(self, entry_id: int, event: int) -> PicksPayload:
        return PicksPayload.model_validate(
            await self._get(f"entry/{entry_id}/event/{event}/picks/")
        )

    async def entry_history(self, entry_id: int) -> EntryHistory:
        return EntryHistory.model_validate(await self._get(f"entry/{entry_id}/history/"))

    async def entry_transfers(self, entry_id: int) -> list[TransferRow]:
        payload = await self._get(f"entry/{entry_id}/transfers/")
        return [TransferRow.model_validate(row) for row in payload]
