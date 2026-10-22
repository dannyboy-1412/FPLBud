from pathlib import Path

import pytest

from perf.harness import Report
from perf.suite import REQUIRED_MODULES, run

PROFILED = (
    ("fplcore.models", "parse_bootstrap"),
    ("fplcore.metrics.compute", "compute_player_metrics"),
    ("fplcore.metrics.compute", "fixture_features_for_gw"),
    ("fplcore.optimise", "solve_for_transfers"),
    ("fplcore.optimise", "optimise_horizon"),
    ("fplcore.optimise", "agent_horizons"),
    ("fplcore.agent.chips", "chip_rebuilds"),
    ("fplcore.stats.insights", "insight_tables"),
)


@pytest.fixture(scope="session")
def performance_report() -> Report:
    return run()


def test_report_lands_in_the_performance_directory(performance_report: Report) -> None:
    html = performance_report.path.read_text(encoding="utf-8")
    assert performance_report.path == Path(__file__).resolve().parent / "report.html"
    assert performance_report.path.is_file()
    assert html.startswith("<!DOCTYPE html>")
    assert "timeit" in html
    assert "cProfile" in html
    assert "<h2>Conclusion</h2>" in html
    assert "What works" in html
    assert "What needs improving" in html
    assert "Potential danger" in html


def test_timeit_covers_each_backend_area(performance_report: Report) -> None:
    html = performance_report.path.read_text(encoding="utf-8")
    seen = {result.module for result in performance_report.results}
    assert seen == set(REQUIRED_MODULES)
    for module in REQUIRED_MODULES:
        assert module in html
    for result in performance_report.results:
        assert result.timing.best_s > 0
        assert result.timing.mean_s > 0
        assert result.timing.loops >= 1
        assert result.timing.repeats >= 1


def test_cprofile_names_a_slow_spot(performance_report: Report) -> None:
    profiled = {(result.module, result.name): result for result in performance_report.results if result.profiled}
    assert set(PROFILED) <= set(profiled)
    for key in PROFILED:
        result = profiled[key]
        assert result.hottest is not None
        assert result.profile_total_s > 0
        assert result.profile_self
        assert result.profile_cumulative
    assert performance_report.slow_spot is not None


def test_skipped_io_is_listed(performance_report: Report) -> None:
    html = performance_report.path.read_text(encoding="utf-8")
    assert "FplClient" in html
    assert "Postgres" in html
    assert "ingest jobs" in html
    assert "entry_cache" in html
    assert "Each repeat calls the function again" in html
