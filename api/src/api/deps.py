from collections.abc import Generator

from fastapi import Request
from psycopg import Connection

from fplcore.db import pooled_connection
from fplcore.settings import Settings, get_settings


def get_settings_dep() -> Settings:
    return get_settings()


def db_conn(request: Request) -> Generator[Connection, None, None]:
    with pooled_connection(request.app.state.db_pool) as conn:
        yield conn
