from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from fplcore.settings import Settings, get_settings

SEARCH_PATH = "fpl, public"

_pool: ConnectionPool | None = None


def _dsn(url: str) -> str:
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    if "sslmode=" in url:
        return url
    glue = "&" if "?" in url else "?"
    return f"{url}{glue}sslmode=require"


def _connect_kwargs(*, autocommit: bool = False) -> dict[str, Any]:
    return {
        "row_factory": dict_row,
        "autocommit": autocommit,
        "prepare_threshold": None,
    }


def connect(settings: Settings | None = None, *, autocommit: bool = False) -> psycopg.Connection:
    cfg = settings or get_settings()
    conn = psycopg.connect(_dsn(cfg.database_url), **_connect_kwargs(autocommit=autocommit))
    set_search_path(conn)
    return conn


async def connect_async(settings: Settings | None = None) -> psycopg.AsyncConnection:
    cfg = settings or get_settings()
    conn = await psycopg.AsyncConnection.connect(
        _dsn(cfg.database_url),
        row_factory=dict_row,
        autocommit=False,
        prepare_threshold=None,
    )
    await conn.execute(f"set search_path to {SEARCH_PATH}")
    return conn


def set_search_path(conn: psycopg.Connection) -> None:
    """SET starts a transaction; the pool drops connections that are left open."""
    previous = conn.autocommit
    conn.autocommit = True
    try:
        try:
            conn.execute(f"set search_path to {SEARCH_PATH}")
        except psycopg.Error:
            conn.execute("set search_path to public")
    finally:
        conn.autocommit = previous


def create_pool(settings: Settings | None = None) -> ConnectionPool:
    global _pool
    if _pool is not None and not _pool.closed:
        return _pool
    cfg = settings or get_settings()
    _pool = ConnectionPool(
        conninfo=_dsn(cfg.database_url),
        min_size=cfg.db_pool_min_size,
        max_size=cfg.db_pool_max_size,
        kwargs=_connect_kwargs(),
        configure=set_search_path,
        open=True,
    )
    return _pool


def get_pool(settings: Settings | None = None) -> ConnectionPool:
    if _pool is None or _pool.closed:
        return create_pool(settings)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.close()
    _pool = None


@contextmanager
def pooled_connection(pool: ConnectionPool | None = None) -> Generator[psycopg.Connection, None, None]:
    active = pool or get_pool()
    conn = active.getconn()
    try:
        set_search_path(conn)
        yield conn
    finally:
        if not conn.closed:
            try:
                conn.rollback()
            except psycopg.Error:
                pass
        active.putconn(conn)
