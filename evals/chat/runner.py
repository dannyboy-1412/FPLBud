"""Run chat cases against a scripted model, or a live one when a key is set."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.chat.tools import tool_set
from evals.chat.cases import all_cases
from fplcore.chat.guard import GroundingFinaliser
from fplcore.chat.loop import LoopFailed, LoopFinished, run_turn
from fplcore.chat.prompt import SYSTEM_PROMPT, ContextView
from fplcore.chat.registry import BoundTool, ToolRegistry, null_connection
from fplcore.chat.testing import ScriptedLlm, text_turn, tool_turn
from fplcore.chat.types import ChatCfg, Message, ToolContext, ToolResult, failure

ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "evals" / "chat" / "cases"


def problems_for(case: dict[str, Any], outcome: LoopFinished | LoopFailed) -> list[str]:
    if isinstance(outcome, LoopFailed):
        return [f"failed {outcome.code}: {outcome.message}"]
    found: list[str] = []
    if outcome.grounding != case["grounding"]:
        found.append(f"grounding {outcome.grounding} != {case['grounding']}")
    text = outcome.text
    if "http://" in text or "https://" in text:
        found.append("answer contains a url")
    for needle in case["contains"]:
        if needle not in text:
            found.append(f"missing {needle!r}")
    used = {item["name"] for item in outcome.tools_used}
    for step in case["tools"]:
        if step["name"] not in used:
            found.append(f"did not call {step['name']}")
    return found


async def run_case(case: dict[str, Any], llm: Any | None = None) -> LoopFinished | LoopFailed:
    scripted = llm is None
    model = llm or _script(case)
    last: LoopFinished | LoopFailed | None = None
    async for item in run_turn(
        [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(role="user", content=case["question"], turn_index=1),
        ],
        llm=model,
        tools=_registry(case),
        cfg=ChatCfg(max_rounds=4, max_tool_calls=4, model="scripted" if scripted else ""),
        ctx=ToolContext(
            user_id="synthetic",
            entry_id=None,
            season_id="2026/27",
            weights={},
            snapshot_id=1,
            data_version=1,
            now=datetime.now(UTC),
            has_team=True,
            thread_id="thread",
        ),
        context=ContextView(season_id="2026/27", decision_gw=9, names={13: "Haaland"}),
        finaliser=GroundingFinaliser(),
        turn_id=1,
        prompt_text=SYSTEM_PROMPT,
    ):
        if isinstance(item, LoopFinished | LoopFailed):
            last = item
    if last is None:
        return LoopFailed("UNAVAILABLE", "no outcome", True)
    return last


def write_case_files() -> None:
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in all_cases():
        grouped.setdefault(str(case["group"]), []).append(case)
    for group, rows in grouped.items():
        (CASE_DIR / f"{group}.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def _script(case: dict[str, Any]) -> ScriptedLlm:
    turns = []
    if case["tools"]:
        turns.append(
            tool_turn(
                *[
                    (f"c{index}", step["name"], step["arguments"])
                    for index, step in enumerate(case["tools"])
                ]
            )
        )
    turns.append(text_turn(case["answer"]))
    if case["grounding"] == "fallback":
        turns.append(text_turn(case["answer"]))
    return ScriptedLlm(turns)


def _registry(case: dict[str, Any]) -> ToolRegistry:
    by_name = {tool.name: tool for tool in tool_set()}
    bound: list[BoundTool] = []
    for step in case["tools"]:
        spec = by_name[step["name"]]
        result = _result(step)
        bound.append(
            BoundTool(
                name=spec.name,
                description=spec.description,
                args_model=spec.args_model,
                handler=_handler(result),
                timeout_s=spec.timeout_s,
            )
        )
    return ToolRegistry(bound, open_conn=null_connection, db_slots=2)


def _handler(result: ToolResult) -> Any:
    def run(ctx: Any, args: Any, conn: Any) -> ToolResult:
        del ctx, args, conn
        return result

    return run


def _result(step: dict[str, Any]) -> ToolResult:
    data = step["data"]
    if not step.get("ok", True):
        return failure(str(data.get("code") or "ERROR"), str(data.get("message") or "The tool failed."))
    return ToolResult(ok=True, data=data, data_version=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("scripted", "live"), default="scripted")
    parser.add_argument("--write-cases", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    if args.write_cases:
        write_case_files()
    selected = all_cases()
    if args.limit:
        selected = selected[: args.limit]
    if args.mode == "live":
        asyncio.run(_live(selected))
        return
    failed = asyncio.run(_scripted(selected))
    if failed:
        raise SystemExit(1)


async def _scripted(selected: list[dict[str, Any]]) -> int:
    failed = 0
    for case in selected:
        outcome = await run_case(case)
        issues = problems_for(case, outcome)
        if issues:
            failed += 1
            print(case["id"], "; ".join(issues))
    print(f"{len(selected) - failed} passed, {failed} failed")
    return failed


async def _live(selected: list[dict[str, Any]]) -> None:
    key = os.environ.get("CHAT_LLM_API_KEY", "")
    if not key:
        raise SystemExit("CHAT_LLM_API_KEY is not set")
    from fplcore.chat.model import OpenAICompatClient

    client = OpenAICompatClient(
        api_key=key,
        base_url=os.environ.get("CHAT_LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.environ.get("CHAT_MODEL", "openai/gpt-4o-mini"),
    )
    try:
        failed = 0
        for case in selected:
            outcome = await run_case(case, client)
            if isinstance(outcome, LoopFailed) or "http://" in outcome.text or "https://" in outcome.text:
                failed += 1
                print(case["id"], "live fail")
        if failed:
            raise SystemExit(1)
    finally:
        await client.aclose()


if __name__ == "__main__":
    main()
