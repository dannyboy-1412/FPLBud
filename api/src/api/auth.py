from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient
from psycopg import Connection

from api.deps import db_conn, get_settings_dep
from fplcore.settings import Settings

_jwks_client: PyJWKClient | None = None
_jwks_failed = False


def _jwks(settings: Settings) -> PyJWKClient | None:
    global _jwks_client, _jwks_failed
    if _jwks_failed:
        return None
    if _jwks_client is None:
        url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        try:
            httpx.get(url, timeout=5).raise_for_status()
            _jwks_client = PyJWKClient(url)
        except Exception:
            _jwks_failed = True
            return None
    return _jwks_client


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    options = {"require": ["exp", "sub"], "verify_aud": True}
    jwks = _jwks(settings)
    try:
        if jwks is not None:
            signing = jwks.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing.key,
                algorithms=["ES256", "RS256", "HS256"],
                audience="authenticated",
                options=options,
            )
    except jwt.PyJWTError:
        pass
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=401, detail="invalid token")
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options=options,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return None
    return value


def current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings_dep),
    conn: Connection = Depends(db_conn),
) -> dict[str, Any]:
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="sign in required")
    payload = decode_access_token(token, settings)
    user_id = UUID(payload["sub"])
    row = conn.execute("select last_active_at from public.profiles where id = %s", [user_id]).fetchone()
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
    else:
        last = row["last_active_at"]
        if last is None or (time.time() - last.timestamp()) > 3600:
            conn.execute(
                "update public.profiles set last_active_at = now() where id = %s",
                [user_id],
            )
    conn.commit()
    return {"id": user_id, "claims": payload}


def optional_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings_dep),
    conn: Connection = Depends(db_conn),
) -> dict[str, Any] | None:
    token = _bearer(authorization)
    if not token:
        return None
    try:
        return current_user(authorization, settings, conn)
    except HTTPException:
        return None
