"""Chat threads and the SSE send endpoint. A turn's connection is closed before the stream starts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from api.chat.auth_dep import chat_user
from api.chat.runtime import ChatRuntime, Refuse
from api.chat.sse import frames
from api.limiter import limiter
from fplcore.db import chat_repo

router = APIRouter()


class ThreadBody(BaseModel):
    title: str | None = Field(default=None, max_length=80)


class SendBody(BaseModel):
    text: str
    client_msg_id: str | None = Field(default=None, max_length=80)


class FeedbackBody(BaseModel):
    value: Literal[-1, 1]
    reason: str | None = Field(default=None, max_length=200)


class MemoryDecision(BaseModel):
    proposal_id: int
    accept: bool = True


def _runtime(request: Request) -> ChatRuntime:
    runtime = getattr(request.app.state, "chat_runtime", None)
    if not isinstance(runtime, ChatRuntime):
        raise HTTPException(status_code=503, detail={"code": "CHAT_DISABLED", "message": "Chat is turned off."})
    return runtime


def _user_id(user: dict[str, Any]) -> str:
    return str(user["id"])


def _thread_id(value: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Thread not found.") from exc


def _refuse(refuse: Refuse) -> HTTPException:
    detail: dict[str, Any] = {"code": refuse.code, "message": refuse.message}
    if refuse.turns_left is not None:
        detail["turns_left_today"] = refuse.turns_left
    if refuse.retryable:
        detail["retryable"] = True
    return HTTPException(status_code=refuse.status_code, detail=detail)


def _enabled(runtime: ChatRuntime, user_id: str) -> None:
    if runtime.enabled_for(user_id):
        return
    raise HTTPException(status_code=503, detail={"code": "CHAT_DISABLED", "message": "Chat is turned off."})


@router.get("/chat/health")
def chat_health(request: Request, user: dict[str, Any] = Depends(chat_user)) -> dict[str, Any]:
    runtime = getattr(request.app.state, "chat_runtime", None)
    enabled = bool(runtime and runtime.enabled_for(_user_id(user)))
    return {"enabled": enabled}


@router.post("/chat/threads")
def create_thread(
    request: Request,
    body: ThreadBody | None = None,
    user: dict[str, Any] = Depends(chat_user),
) -> dict[str, Any]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    title = body.title if body else None
    with runtime.open_conn() as conn:
        row = chat_repo.create_thread(conn, user_id, title)
    return {"id": str(row["id"]), "title": row["title"]}


@router.get("/chat/threads")
def list_threads(request: Request, user: dict[str, Any] = Depends(chat_user)) -> dict[str, Any]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        rows = chat_repo.list_threads(conn, user_id)
    return {"threads": [_thread(row) for row in rows]}


@router.get("/chat/threads/{thread_id}")
def get_thread(request: Request, thread_id: str, user: dict[str, Any] = Depends(chat_user)) -> dict[str, Any]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        thread = chat_repo.get_thread(conn, _thread_id(thread_id), user_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found.")
        messages = chat_repo.visible_messages(conn, str(thread["id"]))
    return {"thread": _thread(thread), "messages": [_message(row) for row in messages]}


@router.delete("/chat/threads/{thread_id}")
def delete_thread(request: Request, thread_id: str, user: dict[str, Any] = Depends(chat_user)) -> Response:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        found = chat_repo.delete_thread(conn, _thread_id(thread_id), user_id)
    if not found:
        raise HTTPException(status_code=404, detail="Thread not found.")
    return Response(status_code=204)


@router.delete("/chat/threads")
def delete_all_threads(request: Request, user: dict[str, Any] = Depends(chat_user)) -> dict[str, int]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        deleted = chat_repo.delete_all_threads(conn, user_id)
    return {"deleted": deleted}


@router.post("/chat/threads/{thread_id}/messages")
@limiter.limit("4/minute")
async def send_message(
    request: Request,
    thread_id: str,
    body: SendBody,
    user: dict[str, Any] = Depends(chat_user),
    x_fplbud_client: str | None = Header(default=None, alias="X-FPLBud-Client"),
) -> StreamingResponse:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    if not await runtime.acquire():
        raise HTTPException(
            status_code=503,
            detail={"code": "BUSY", "message": "Chat is busy. Try again in a moment.", "retryable": True},
        )
    try:
        prepared = await runtime.prepare(
            user_id=user_id,
            thread_id=_thread_id(thread_id),
            text=body.text,
            client_msg_id=body.client_msg_id,
            client=x_fplbud_client,
        )
    except Exception:
        runtime.release()
        raise
    if isinstance(prepared, Refuse):
        runtime.release()
        raise _refuse(prepared)

    async def body_stream() -> Any:
        try:
            async for chunk in frames(runtime.events(prepared)):
                yield chunk
        finally:
            runtime.release()

    if prepared.kind == "replay":
        runtime.release()

        async def replay_stream() -> Any:
            async for chunk in frames(runtime.events(prepared)):
                yield chunk

        return _sse(replay_stream())
    return _sse(body_stream())


@router.post("/chat/messages/{message_id}/feedback")
def feedback(
    request: Request,
    message_id: int,
    body: FeedbackBody,
    user: dict[str, Any] = Depends(chat_user),
) -> dict[str, bool]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        saved = chat_repo.set_feedback(conn, message_id, user_id, body.value, body.reason)
    if not saved:
        raise HTTPException(status_code=404, detail="Message not found.")
    return {"ok": True}


@router.get("/chat/usage")
def usage(request: Request, user: dict[str, Any] = Depends(chat_user)) -> dict[str, Any]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        today = chat_repo.usage_today(conn, user_id)
        has_team = chat_repo.latest_snapshot(conn, user_id) is not None
    cap = runtime.settings.chat_user_turns_per_day if has_team else runtime.settings.chat_user_turns_per_day_noteam
    used = int(today["turns"])
    return {
        "turns_used": used,
        "turns_left": max(0, cap - used),
        "daily_cap": cap,
        "optimiser_calls": int(today["optimiser_calls"]),
        "resets_at": "00:00 UTC",
    }


@router.get("/chat/memory")
def list_memory(request: Request, user: dict[str, Any] = Depends(chat_user)) -> dict[str, Any]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        rows = chat_repo.list_memory(conn, user_id)
    return {"memory": [{"key": row["key"], "value": row["value"]} for row in rows]}


@router.post("/chat/memory/confirm")
def confirm_memory(
    request: Request,
    body: MemoryDecision,
    user: dict[str, Any] = Depends(chat_user),
) -> dict[str, Any]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        if body.accept:
            saved = chat_repo.confirm_proposal(conn, body.proposal_id, user_id)
            if saved is None:
                raise HTTPException(status_code=404, detail="That preference expired.")
            return {"ok": True, **saved}
        dismissed = chat_repo.dismiss_proposal(conn, body.proposal_id, user_id)
    if not dismissed:
        raise HTTPException(status_code=404, detail="That preference expired.")
    return {"ok": True}


@router.delete("/chat/memory")
def delete_memory(
    request: Request,
    user: dict[str, Any] = Depends(chat_user),
    key: str | None = None,
) -> dict[str, int]:
    runtime = _runtime(request)
    user_id = _user_id(user)
    _enabled(runtime, user_id)
    with runtime.open_conn() as conn:
        if key:
            deleted = 1 if chat_repo.delete_memory(conn, user_id, key) else 0
        else:
            deleted = chat_repo.delete_all_memory(conn, user_id)
    return {"deleted": deleted}


def _sse(source: Any) -> StreamingResponse:
    return StreamingResponse(
        source,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _thread(row: dict[str, Any]) -> dict[str, Any]:
    updated = row.get("updated_at")
    return {
        "id": str(row["id"]),
        "title": row.get("title"),
        "message_count": row.get("message_count", 0),
        "updated_at": updated.isoformat() if isinstance(updated, datetime) else updated,
    }


def _message(row: dict[str, Any]) -> dict[str, Any]:
    created = row.get("created_at")
    return {
        "id": int(row["id"]),
        "role": row["role"],
        "content": row["content"],
        "citations": row.get("citations") or [],
        "feedback": row.get("feedback"),
        "created_at": created.isoformat() if isinstance(created, datetime) else created,
    }
