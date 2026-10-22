"""timeit and cProfile helpers for the backend performance suite."""

from __future__ import annotations

import cProfile
import pstats
import statistics
import timeit
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Timing:
    loops: int
    repeats: int
    best_s: float
    mean_s: float
    stdev_s: float


@dataclass(frozen=True)
class ProfileEntry:
    function: str
    location: str
    calls: int
    tottime_s: float
    cumtime_s: float


@dataclass(frozen=True)
class Job:
    name: str
    module: str
    workload: str
    call: Callable[[], object]
    repeats: int = 5
    loops: int | None = None
    profile: bool = False
    suspect: str = ""


@dataclass(frozen=True)
class Result:
    name: str
    module: str
    workload: str
    suspect: str
    timing: Timing
    profiled: bool
    profile_self: tuple[ProfileEntry, ...]
    profile_cumulative: tuple[ProfileEntry, ...]
    profile_total_s: float

    @property
    def hottest(self) -> ProfileEntry | None:
        """Function that spent the most time in its own body, excluding the suite."""
        for entry in self.profile_self:
            if entry.location.startswith("perf/"):
                continue
            return entry
        if self.profile_self:
            return self.profile_self[0]
        return None

    @property
    def dominant_callee(self) -> ProfileEntry | None:
        """Project function that owns the most of this run, excluding the function itself."""
        best: ProfileEntry | None = None
        for entry in self.profile_cumulative:
            if not _project_location(entry.location):
                continue
            if (
                entry.function == self.name
                and self.profile_total_s > 0
                and entry.cumtime_s >= self.profile_total_s * 0.9
            ):
                continue
            if best is None or entry.cumtime_s > best.cumtime_s:
                best = entry
        return best


@dataclass(frozen=True)
class Report:
    path: Path
    results: tuple[Result, ...]
    dataset: str
    load_s: float
    elapsed_s: float
    generated_at: str
    python_version: str
    platform_name: str

    @property
    def slowest(self) -> Result:
        return max(self.results, key=lambda result: result.timing.mean_s)

    @property
    def slow_spot(self) -> tuple[Result, ProfileEntry] | None:
        found: tuple[Result, ProfileEntry] | None = None
        for result in self.results:
            spot = result.hottest
            if spot is None:
                continue
            if found is None or spot.tottime_s > found[1].tottime_s:
                found = (result, spot)
        return found


def format_seconds(value: float) -> str:
    if value >= 1:
        return f"{value:.3f} s"
    if value >= 1e-3:
        return f"{value * 1e3:.2f} ms"
    if value >= 1e-6:
        return f"{value * 1e6:.1f} us"
    return f"{value * 1e9:.1f} ns"


def measure(call: Callable[[], object], *, loops: int | None, repeats: int) -> Timing:
    """Time ``call`` with timeit.

    Slow calls pass a fixed ``loops`` of 1. Faster calls leave it unset so
    timeit picks a loop count that is long enough to measure.
    """
    timer = timeit.Timer(call)
    chosen = loops if loops is not None else timer.autorange()[0]
    samples = [duration / chosen for duration in timer.repeat(repeat=repeats, number=chosen)]
    return Timing(
        loops=chosen,
        repeats=repeats,
        best_s=min(samples),
        mean_s=statistics.fmean(samples),
        stdev_s=statistics.stdev(samples) if len(samples) > 1 else 0.0,
    )


def profile(
    call: Callable[[], object], *, limit: int = 12
) -> tuple[tuple[ProfileEntry, ...], tuple[ProfileEntry, ...], float]:
    """Run ``call`` once under cProfile.

    Returns the functions with the most self time, the functions with the most
    cumulative time, and the cumulative time of the outermost call.
    """
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        call()
    finally:
        profiler.disable()

    stats = pstats.Stats(profiler)
    entries: list[ProfileEntry] = []
    total = 0.0
    for key, value in stats.stats.items():
        filename, line, name = key
        calls, _primitive, tottime, cumtime, _callers = value
        if name in _SKIPPED_PROFILE_NAMES:
            continue
        total = max(total, float(cumtime))
        entries.append(
            ProfileEntry(
                function=name,
                location=_location(str(filename), int(line)),
                calls=int(calls),
                tottime_s=float(tottime),
                cumtime_s=float(cumtime),
            )
        )
    by_self = tuple(sorted(entries, key=lambda entry: entry.tottime_s, reverse=True)[:limit])
    by_cumulative = tuple(sorted(entries, key=lambda entry: entry.cumtime_s, reverse=True)[:limit])
    return by_self, by_cumulative, total


_SKIPPED_PROFILE_NAMES = {
    "<method 'disable' of '_lsprof.Profiler' objects>",
    "<method 'enable' of '_lsprof.Profiler' objects>",
}


def _project_location(location: str) -> bool:
    return any(marker in location for marker in ("fplcore/", "api/src/", "ingest/src/"))


def _location(filename: str, line: int) -> str:
    name = filename.replace("\\", "/")
    for marker in ("perf/", "fplcore/src/", "api/src/", "ingest/src/", "site-packages/"):
        index = name.find(marker)
        if index >= 0:
            return f"{name[index:]}:{line}"
    return f"{name.rsplit('/', 1)[-1]}:{line}"
