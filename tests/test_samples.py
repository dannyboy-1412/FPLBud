import json
from pathlib import Path

from fplcore.models import (
    BootstrapStatic,
    ElementSummary,
    Entry,
    EntryHistory,
    Fixture,
    PicksPayload,
)

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def test_bootstrap_sample_parses() -> None:
    path = SAMPLES / "bootstrap-static.json"
    if not path.exists():
        return
    data = BootstrapStatic.model_validate_json(path.read_text(encoding="utf-8"))
    assert data.elements
    assert data.teams
    assert data.events


def test_entry_samples_parse() -> None:
    if not (SAMPLES / "entry.json").exists():
        return
    Entry.model_validate_json((SAMPLES / "entry.json").read_text(encoding="utf-8"))
    PicksPayload.model_validate_json((SAMPLES / "picks.json").read_text(encoding="utf-8"))
    EntryHistory.model_validate_json((SAMPLES / "history.json").read_text(encoding="utf-8"))
    ElementSummary.model_validate_json((SAMPLES / "element-summary.json").read_text(encoding="utf-8"))
    payload = json.loads((SAMPLES / "fixtures.json").read_text(encoding="utf-8"))
    assert Fixture.model_validate(payload[0]).id
