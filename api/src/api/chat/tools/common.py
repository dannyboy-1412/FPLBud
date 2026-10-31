from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from fplcore.chat.types import ToolResult


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def ok(
    data: dict[str, Any],
    *,
    as_of: str | None,
    data_version: int | None,
    notes: list[str] | None = None,
) -> ToolResult:
    return ToolResult(ok=True, data=data, as_of=as_of, data_version=data_version, notes=list(notes or []))
