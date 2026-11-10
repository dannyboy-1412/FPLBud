from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from fplcore.chat.budget import estimate_tokens
from fplcore.chat.cache import activate_cache, reset_cache
from fplcore.chat.guard import sanitise_tree
from fplcore.chat.types import (
    OPTIMISER_TOOL,
    ToolCall,
    ToolContext,
    ToolResult,
    TurnCounters,
    failure,
)

logger = logging.getLogger("fplbud.chat")

ConnFactory = Callable[[], Any]
SpanRecorder = Callable[[Any, dict[str, Any]], None]


@dataclass
class BoundTool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, BaseModel, Any], ToolResult]
    timeout_s: float = 8.0
    risk: str = "low"


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema with every property required and additionalProperties false."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    schema = _resolve(raw, defs)
    if isinstance(schema, dict):
        _strictify(schema)
        schema.pop("title", None)
    return schema if isinstance(schema, dict) else {"type": "object", "additionalProperties": False}


def _resolve(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = str(node["$ref"]).rsplit("/", 1)[-1]
            return _resolve(defs[name], defs)
        return {key: _resolve(value, defs) for key, value in node.items() if key != "title"}
    if isinstance(node, list):
        return [_resolve(item, defs) for item in node]
    return node


def _strictify(schema: dict[str, Any]) -> None:
    if schema.get("type") == "object" or "properties" in schema:
        properties = schema.get("properties") or {}
        schema["type"] = "object"
        schema["properties"] = properties
        schema["additionalProperties"] = False
        schema["required"] = list(properties)
        for prop in properties.values():
            if isinstance(prop, dict):
                _collapse_null(prop)
                _strictify(prop)
    items = schema.get("items")
    if isinstance(items, dict):
        _strictify(items)
    schema.pop("default", None)


def _collapse_null(prop: dict[str, Any]) -> None:
    options = prop.get("anyOf")
    if not isinstance(options, list):
        return
    types: list[str] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        if option.get("type") == "null":
            types.append("null")
            continue
        if "type" in option:
            types.append(str(option["type"]))
        for key in ("enum", "maxLength", "minimum", "maximum", "description", "items"):
            if key in option and key not in prop:
                prop[key] = option[key]
    if not types:
        return
    prop.pop("anyOf", None)
    prop["type"] = types if len(types) > 1 else types[0]


def openai_tool(tool: BoundTool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": strict_schema(tool.args_model),
            "strict": True,
        },
    }


class ToolRegistry:
    """Validates, memoises, times out and sanitises every tool call."""

    def __init__(
        self,
        tools: list[BoundTool],
        *,
        open_conn: ConnFactory,
        db_slots: int = 4,
        optimiser_slots: int = 1,
        max_optimiser_calls: int = 2,
        result_soft_cap: int = 1500,
        result_hard_cap: int = 3000,
        record_span: SpanRecorder | None = None,
    ) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._order = [tool.name for tool in tools]
        self._open_conn = open_conn
        self._db_slots = asyncio.Semaphore(max(db_slots, 1))
        self._optimiser = asyncio.Semaphore(max(optimiser_slots, 1))
        self._flight: dict[str, asyncio.Future[ToolResult]] = {}
        self._flight_lock = asyncio.Lock()
        self._max_optimiser_calls = max_optimiser_calls
        self._soft_cap = result_soft_cap
        self._hard_cap = result_hard_cap
        self._record_span = record_span

    def specs(self) -> list[dict[str, Any]]:
        return [openai_tool(self._tools[name]) for name in self._order]

    def has(self, name: str) -> bool:
        return name in self._tools

    def labels(self) -> dict[str, str]:
        return {name: self._tools[name].description.split(".")[0] for name in self._order}

    async def execute(
        self,
        call: ToolCall,
        ctx: ToolContext,
        seen: dict[str, ToolResult],
        counters: TurnCounters,
        *,
        turn_id: int | None = None,
        round_no: int = 1,
    ) -> ToolResult:
        counters.tool_calls += 1
        tool = self._tools.get(call.name)
        if tool is None:
            return failure(
                "UNKNOWN_TOOL",
                f"No tool named {call.name}.",
                hint="Valid tools: " + ", ".join(self._order),
            )
        if call.parse_error or call.arguments is None:
            return failure("INVALID_ARGUMENT", call.parse_error or "Arguments were not JSON.")
        try:
            args = tool.args_model.model_validate(call.arguments)
        except ValidationError as exc:
            return _invalid(exc)
        key = call.name + "\n" + args.model_dump_json()
        async with self._flight_lock:
            prior = seen.get(key)
            if prior is not None:
                return _memo(prior)
            leader_box = self._flight.get(key)
            if leader_box is None:
                leader_box = asyncio.get_running_loop().create_future()
                self._flight[key] = leader_box
                leading = True
            else:
                leading = False
        if not leading:
            return _memo(await leader_box)
        try:
            if call.name == OPTIMISER_TOOL and counters.optimiser_calls >= self._max_optimiser_calls:
                result = failure(
                    "RATE_LIMITED",
                    "The optimiser has already run enough times this question.",
                    hint="Use get_plan_suggestions.",
                )
            else:
                started = time.perf_counter()
                result = await self._invoke(tool, ctx, args, call.name)
                result.duration_ms = int((time.perf_counter() - started) * 1000)
                result = _cap_result(result, soft=self._soft_cap, hard=self._hard_cap)
                if call.name == OPTIMISER_TOOL and result.ok:
                    counters.optimiser_calls += 1
        except Exception:
            logger.exception("chat tool failed name=%s", call.name)
            result = failure("INTERNAL", "The tool failed. Answer without it.")
        async with self._flight_lock:
            seen[key] = result
            self._flight.pop(key, None)
        if not leader_box.done():
            leader_box.set_result(result)
        self._span(turn_id, round_no, call, args, result)
        return result

    async def _invoke(self, tool: BoundTool, ctx: ToolContext, args: BaseModel, name: str) -> ToolResult:
        def work() -> ToolResult:
            with self._open_conn() as conn:
                return tool.handler(ctx, args, conn)

        token = activate_cache(ctx.cache) if ctx.cache is not None else None
        try:
            if name == OPTIMISER_TOOL:
                async with self._optimiser, self._db_slots:
                    raw = await asyncio.wait_for(asyncio.to_thread(work), timeout=tool.timeout_s)
            else:
                async with self._db_slots:
                    raw = await asyncio.wait_for(asyncio.to_thread(work), timeout=tool.timeout_s)
        except TimeoutError:
            hint = "Use get_plan_suggestions." if name == OPTIMISER_TOOL else "Try a narrower question."
            return failure("TIMEOUT", "That lookup took too long.", hint=hint)
        except Exception:
            logger.exception("chat tool failed name=%s", name)
            return failure("INTERNAL", "The tool failed. Answer without it.", hint="Tell the user what is missing.")
        finally:
            if token is not None:
                reset_cache(token)
        cleaned, suspected = sanitise_tree(raw.data)
        if isinstance(cleaned, dict):
            raw.data = cleaned
        raw.injection_suspected = raw.injection_suspected or suspected
        return raw

    def _span(
        self,
        turn_id: int | None,
        round_no: int,
        call: ToolCall,
        args: BaseModel,
        result: ToolResult,
    ) -> None:
        if self._record_span is None or turn_id is None:
            return
        payload = {
            "turn_id": turn_id,
            "round": round_no,
            "name": call.name,
            "args": args.model_dump(mode="json"),
            "ok": result.ok,
            "error_code": result.error.code if result.error else None,
            "result_tokens": estimate_tokens(result.to_model_text()),
            "result": result.envelope(),
            "duration_ms": result.duration_ms,
            "injection_suspected": result.injection_suspected,
        }
        try:
            with self._open_conn() as conn:
                self._record_span(conn, payload)
        except Exception:
            logger.exception("chat span persist failed")


def _invalid(exc: ValidationError) -> ToolResult:
    err = exc.errors()[0] if exc.errors() else {}
    message = str(err.get("msg") or "Invalid arguments.")
    expected = (err.get("ctx") or {}).get("expected") if isinstance(err.get("ctx"), dict) else None
    hint = f"Valid values: {expected}." if expected else "Check the argument types and try once more."
    return failure("INVALID_ARGUMENT", message, hint=hint)


def _memo(prior: ToolResult) -> ToolResult:
    return ToolResult(
        ok=prior.ok,
        data=prior.data,
        error=prior.error,
        as_of=prior.as_of,
        data_version=prior.data_version,
        notes=[*prior.notes, "identical call already made; use the earlier result"],
        truncated=prior.truncated,
        duration_ms=prior.duration_ms,
        injection_suspected=prior.injection_suspected,
    )


def _cap_result(result: ToolResult, *, soft: int, hard: int) -> ToolResult:
    if not result.ok or result.data is None:
        return result
    if estimate_tokens(result.to_model_text()) <= soft:
        return result
    data = dict(result.data)
    notes = list(result.notes)
    for _ in range(6):
        shrunk = False
        for key, value in list(data.items()):
            if isinstance(value, list) and len(value) > 1:
                data[key] = value[: max(1, len(value) // 2)]
                shrunk = True
        if not shrunk:
            break
        trial = ToolResult(
            ok=True,
            data=data,
            as_of=result.as_of,
            data_version=result.data_version,
            notes=notes,
            truncated=True,
            duration_ms=result.duration_ms,
            injection_suspected=result.injection_suspected,
        )
        if estimate_tokens(trial.to_model_text()) <= hard:
            trial.notes = [*notes, "Result truncated. Narrow the query."]
            return trial
    result.truncated = True
    result.notes = [*result.notes, "Result truncated. Narrow the query."]
    result.data = {"note": "Result was too large. Ask for fewer players or one named player."}
    return result


@contextmanager
def null_connection() -> Any:
    yield None
