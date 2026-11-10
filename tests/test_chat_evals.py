import asyncio
from pathlib import Path

from evals.chat.cases import all_cases
from evals.chat.golden import transcript
from evals.chat.runner import problems_for, run_case, write_case_files

ROOT = Path(__file__).resolve().parents[1]


def test_golden_sse_matches_the_framer() -> None:
    saved = (ROOT / "contracts" / "chat" / "sse" / "deadline.sse").read_text(encoding="utf-8")
    assert saved == transcript()


def test_case_set_covers_core_and_plans() -> None:
    cases = all_cases()
    assert len(cases) == 48
    assert sum(1 for case in cases if case["group"] == "core") == 25
    assert sum(1 for case in cases if case["group"] == "plans") == 15
    assert sum(1 for case in cases if case["group"] == "tools") == 8


def test_scripted_cases_pass() -> None:
    write_case_files()
    failures: list[str] = []

    async def run_all() -> None:
        for case in all_cases():
            outcome = await run_case(case)
            issues = problems_for(case, outcome)
            if issues:
                failures.append(f"{case['id']}: {'; '.join(issues)} text={getattr(outcome, 'text', '')[:180]}")

    asyncio.run(run_all())
    assert failures == []
    assert (ROOT / "evals" / "chat" / "cases" / "core.json").exists()
    assert (ROOT / "evals" / "chat" / "cases" / "plans.json").exists()
    assert (ROOT / "evals" / "chat" / "cases" / "tools.json").exists()
