from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.limiter import limiter
from api.routers import agent, health, me, meta, players, public, stats, suggestions
from api.worker import poll_loop
from fplcore.db import close_pool, create_pool
from fplcore.settings import get_settings

# Browsers that may call this API with credentials. Add the deployed site here.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
    app.state.settings = settings
    app.state.db_pool = create_pool(settings)
    app.state.started_at = datetime.now(UTC)
    task = asyncio.create_task(poll_loop(settings))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    close_pool()


def create_app() -> FastAPI:
    app = FastAPI(title="FPLBud API", version="0.1.0", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOWED_ORIGINS,
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
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
