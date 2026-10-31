from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.chat.runtime import build_chat_runtime
from api.limiter import limiter
from api.routers import agent, chat, health, me, meta, players, public, stats, suggestions
from api.worker import poll_loop
from fplcore.db import close_pool, create_pool
from fplcore.settings import get_settings

# Preview deploys use a different host than the production alias.
VERCEL_PREVIEW_ORIGIN = r"https://fplbud(?:-[a-z0-9-]+)?\.vercel\.app"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            send_default_pii=False,
            before_send=_scrub_chat,  # type: ignore[arg-type]
        )
    app.state.settings = settings
    app.state.db_pool = create_pool(settings)
    app.state.chat_runtime = build_chat_runtime(settings, app.state.db_pool)
    app.state.started_at = datetime.now(UTC)
    task = asyncio.create_task(poll_loop(settings))
    yield
    runtime = app.state.chat_runtime
    if runtime is not None:
        await runtime.aclose()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FPLBud API", version="0.1.0", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=VERCEL_PREVIEW_ORIGIN,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(meta.router)
    app.include_router(public.router)
    app.include_router(suggestions.router)
    app.include_router(players.router)
    app.include_router(stats.router)
    app.include_router(me.router)
    app.include_router(agent.router)
    app.include_router(chat.router)
    return app


def _scrub_chat(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    del hint
    request = event.get("request")
    url = ""
    if isinstance(request, dict):
        url = str(request.get("url") or "")
        if "/chat" in url:
            request.pop("data", None)
    return event


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
