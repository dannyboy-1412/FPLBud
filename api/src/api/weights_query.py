from __future__ import annotations

import json
import math

from fastapi import HTTPException

from fplcore.constants import ALL_METRICS


def parse_weights_query(raw: str | None) -> dict[str, float] | None:
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="weights must be a JSON object") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="weights must be a JSON object")
    weights: dict[str, float] = {}
    for key, value in payload.items():
        if key not in ALL_METRICS:
            raise HTTPException(status_code=422, detail=f"unknown weight: {key}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(status_code=422, detail=f"weight {key} must be a number")
        number = float(value)
        if math.isnan(number) or math.isinf(number) or number < 0:
            raise HTTPException(status_code=422, detail=f"weight {key} must be non-negative")
        weights[key] = number
    return weights
