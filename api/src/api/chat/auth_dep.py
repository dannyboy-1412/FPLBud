"""Auth for chat routes. The stream must not use the yield db_conn dependency."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request

from api.auth import decode_access_token
from api.deps import get_settings_dep
from fplcore.db import pooled_connection
from fplcore.settings import Settings


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return None
    return value


def chat_user(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, Any]:
    """Verify the JWT and release the pooled connection before the response starts."""
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="sign in required")
    payload = decode_access_token(token, settings)
    user_id = UUID(str(payload["sub"]))
    pool = getattr(request.app.state, "db_pool", None)
    if pool is not None:
        with pooled_connection(pool) as conn:
            _touch_profile(conn, user_id, payload)
            conn.commit()
    return {"id": user_id, "claims": payload}


def _touch_profile(conn: Any, user_id: UUID, payload: dict[str, Any]) -> None:
    row = conn.execute(
        "select last_active_at from public.profiles where id = %s",
        [user_id],
    ).fetchone()
    if row is None:
        meta = payload.get("user_metadata") or {}
        conn.execute(
            """
            insert into public.profiles (id, display_name, avatar_url)
            values (%s, %s, %s)
            on conflict (id) do nothing
            """,
            [user_id, meta.get("full_name") or meta.get("name"), meta.get("avatar_url")],
        )
        return
    last = row["last_active_at"]
    if last is None or (time.time() - last.timestamp()) > 3600:
        conn.execute(
            "update public.profiles set last_active_at = now() where id = %s",
            [user_id],
        )
