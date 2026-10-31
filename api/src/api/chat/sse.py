"""Server-sent events for one chat turn. Comments are heartbeats, not events."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from pydantic import BaseModel

from fplcore.chat.events import event_name, event_payload

HEARTBEAT_SECONDS = 15.0


def frame(event: BaseModel) -> str:
    payload = json.dumps(event_payload(event), separators=(",", ":"), default=str)
    return f"event: {event_name(event)}\ndata: {payload}\n\n"


def heartbeat() -> str:
    return ": ping\n\n"


async def frames(
    events: AsyncIterator[BaseModel],
    *,
    interval: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Turn typed events into SSE bytes, with a comment if the turn goes quiet."""
    agen = events.__aiter__()
    pending: asyncio.Future[BaseModel] = asyncio.ensure_future(agen.__anext__())
    try:
        while True:
            done, _pending = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield heartbeat()
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            pending = asyncio.ensure_future(agen.__anext__())
            yield frame(event)
    finally:
        if not pending.done():
            pending.cancel()
        try:
            await pending
        except (asyncio.CancelledError, StopAsyncIteration):
            pass
        close = getattr(agen, "aclose", None)
        if close is not None:
            await close()
