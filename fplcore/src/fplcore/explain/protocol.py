from __future__ import annotations

from typing import Any, Protocol


class HorizonResult(dict[str, Any]):
    """Structured result for one horizon. Keys match HorizonPlan plus reason_codes."""


class Explainer(Protocol):
    source: str

    def explain(self, result: HorizonResult) -> str: ...

    def explain_run(self, results: dict[str, HorizonResult]) -> dict[str, str]:
        return {key: self.explain(value) for key, value in results.items()}
