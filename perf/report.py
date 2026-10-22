"""HTML report for one performance-suite run."""

from __future__ import annotations

import html
from pathlib import Path

from perf.harness import ProfileEntry, Report, Result, format_seconds

# Paths that talk to Postgres, the FPL API, or an LLM. The CPU they wrap is timed elsewhere.
SKIPPED = (
    (
        "fplcore.client.FplClient",
        "HTTP to the public FPL API. Token-bucket acquire is timed on its own.",
    ),
    (
        "fplcore.db connection and SQL",
        "Postgres. season_id_from_bootstrap, retention_windows and round_points_from_history are timed.",
    ),
    (
        "fplcore.agent.queue and runner",
        "Postgres, then the optimiser and chip advice measured above. The weights hash is timed.",
    ),
    (
        "fplcore.explain.llm async path",
        "External LLM HTTP. Template text, JSON parsing and grounding checks are timed.",
    ),
    (
        "fplcore.lineup.choose_lineup",
        "Calls the optimiser or the LLM. Lineup validation and the solver are timed.",
    ),
    (
        "api routes, auth and the worker",
        "HTTP, JWT and Postgres around the shaping, weights and rate-limit functions that are timed.",
    ),
    (
        "ingest jobs",
        "HTTP and Postgres. The metric recompute they call is timed as compute_player_metrics.",
    ),
)

# Production caches this command does not exercise. Timings are a fresh call every repeat.
CACHES = (
    (
        "Result cache",
        "None. Each repeat calls the function again. Plans and metric rows are not kept for the next repeat.",
    ),
    (
        "entry_cache",
        "Postgres, five minutes, public FPL entry payloads. This command never opens it.",
    ),
    (
        "Suggested XI cache",
        "Postgres row for a squad and its weights. This command never opens it.",
    ),
    (
        "Settings",
        "get_settings() is cached for the process. The settings row calls Settings() directly, so it does not use that cache.",
    ),
    (
        "Next.js and the FPL CDN",
        "The web app and the live API. Samples are local files.",
    ),
)


def write_report(report: Report) -> Path:
    """Write every timing and profile to a single HTML file."""
    path = report.path
    temporary = path.with_suffix(".html.tmp")
    temporary.write_text(_page(report), encoding="utf-8")
    temporary.replace(path)
    return path


def _page(report: Report) -> str:
    slowest = report.slowest
    finding = _finding(slowest)
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>FPLBud backend performance</title>",
        "<style>" + _CSS + "</style>",
        "</head>",
        "<body>",
        "<h1>FPLBud backend performance</h1>",
        "<p class='note'>Backend CPU only. Uninstrumented timeit for every measured function, "
        "cProfile where the time is likely to hide inside a call. "
        "A guest suggestion or a saved-team plan also waits on Postgres, and a cold team import waits on the FPL API. "
        "Best is the fastest repeat. Mean and stdev show how far the repeats moved. "
        "These numbers are a measurement from this machine, not a pass/fail budget.</p>",
        "<div class='lead'>",
        f"<p><strong>Dataset.</strong> {_esc(report.dataset)}. "
        f"Sample setup {_esc(format_seconds(report.load_s))}. "
        f"Suite wall time {_esc(format_seconds(report.elapsed_s))}.</p>",
        f"<p><strong>Slowest call.</strong> <code>{_esc(slowest.module)}.{_esc(slowest.name)}</code> "
        f"mean {_esc(format_seconds(slowest.timing.mean_s))}, "
        f"best {_esc(format_seconds(slowest.timing.best_s))}.</p>",
        f"<p><strong>Slow spot.</strong> {finding}</p>",
        f"<p class='note'>{_esc(report.generated_at)} · Python {_esc(report.python_version)} · "
        f"{_esc(report.platform_name)}</p>",
        "</div>",
        "<section>",
        "<h2>Slowest calls</h2>",
        _results_table(sorted(report.results, key=lambda item: item.timing.mean_s, reverse=True)),
        "</section>",
        "<section>",
        "<h2>cProfile</h2>",
        "<p class='note'>One instrumented run each. Self time is time inside the function, "
        "excluding functions it calls. Cumulative time includes those calls. "
        "Python-heavy profiles run slower than the timeit column because the profiler is on. "
        "Use the timeit column to compare calls.</p>",
        _profiles(report),
        "</section>",
        "<section>",
        "<h2>All results by module</h2>",
        _results_table(sorted(report.results, key=lambda item: (item.module, item.name))),
        "</section>",
        "<section>",
        "<h2>Caching</h2>",
        "<p class='note'>Nothing in this run is served from an application cache. "
        "A faster second repeat is the machine keeping the CBC solver program in its file cache, "
        "not a stored plan.</p>",
        _pair_table(CACHES, "Layer", "What this command does"),
        "</section>",
        "<section>",
        "<h2>Not measured</h2>",
        "<p class='note'>These paths wait on the network or Postgres. "
        "Timing them here would measure the connection, not the backend.</p>",
        _skipped_table(),
        "</section>",
        _conclusion(report),
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)


def _conclusion(report: Report) -> str:
    found = {result.name: result for result in report.results}
    quick = sum(1 for result in report.results if result.timing.mean_s < 0.05)
    return "\n".join(
        [
            "<section>",
            "<h2>Conclusion</h2>",
            "<h3>What works</h3>",
            f"<p>{_works(found, quick, len(report.results))}</p>",
            "<h3>What needs improving</h3>",
            f"<p>{_improve(found)}</p>",
            "<h3>Potential danger</h3>",
            f"<p>{_danger(found)}</p>",
            "</section>",
        ]
    )


def _works(found: dict[str, Result], quick: int, total: int) -> str:
    horizon = found.get("optimise_horizon")
    plan = (
        f"A next-gameweek plan is {_mean(horizon)} of solver CPU."
        if horizon is not None
        else "The next-gameweek plan was not measured."
    )
    return (
        f"{plan} That is the guest request's maths, before Postgres. "
        f"{quick} of the {total} measured calls finish in under 50 ms, "
        "including team import, explanations, stats and the response shape. "
        "Narrowing the squad to a shortlist before the solver is noise next to the solve itself."
    )


def _improve(found: dict[str, Result]) -> str:
    metrics = found.get("compute_player_metrics")
    fixtures = found.get("fixture_features_for_gw")
    form = found.get("compute_form_raw")
    sentences: list[str] = []
    if metrics is not None and fixtures is not None and metrics.timing.mean_s > 0:
        share = fixtures.timing.mean_s / metrics.timing.mean_s * 100
        sentences.append(
            f"Recomputing every player's metrics takes {_mean(metrics)}. "
            f"Fixture scoring is {_mean(fixtures)} of that ({share:.0f}%), "
            "because it walks players in Python and writes one pandas cell at a time."
        )
    if form is not None:
        sentences.append(
            f"Form is the next metric cost at {_mean(form)}, a Python loop over recent appearances."
        )
    if not sentences:
        return "No metric timings were recorded."
    return " ".join(sentences)


def _danger(found: dict[str, Result]) -> str:
    chips = found.get("chip_rebuilds")
    agent = found.get("agent_horizons")
    chip_cost = _mean(chips) if chips is not None else "unmeasured"
    agent_cost = _mean(agent) if agent is not None else "unmeasured"
    return (
        f"Chip advice that may play a free hit or a wildcard takes {chip_cost} for one call. "
        "Each of those chips solves the squad sixteen times. "
        "The worker asks for chip advice after every horizon, so a free hit rebuild runs for horizons 1, 3 and 5, "
        "and a wildcard rebuild runs again on horizon 5. "
        f"The three horizon solves are another {agent_cost}. "
        "That cost belongs in the background agent. "
        "On the guest request, which has to stay well under a second, it would miss the budget, "
        "and it stacks when many saved teams are queued together."
    )


def _mean(result: Result | None) -> str:
    if result is None:
        return "unmeasured"
    return format_seconds(result.timing.mean_s)


def _results_table(results: list[Result]) -> str:
    peak = max(result.timing.mean_s for result in results)
    rows = ["<table>", "<thead><tr>", *_header_cells(), "</tr></thead>", "<tbody>"]
    for result in results:
        width = 0.0 if peak <= 0 else result.timing.mean_s / peak * 100
        label = _esc(result.name)
        if result.profiled:
            label = f'<a href="#{_anchor(result)}">{label}</a>'
        suspect = ""
        if result.suspect:
            suspect = f"<div class='note'><span class='badge'>suspected</span> {_esc(result.suspect)}</div>"
        rows.append(
            "<tr>"
            f"<td>{_esc(result.module)}</td>"
            f"<td>{label}{suspect}<div class='note'>{_esc(result.workload)}</div></td>"
            f"<td class='num'>{_esc(format_seconds(result.timing.best_s))}</td>"
            f"<td class='num'>{_esc(format_seconds(result.timing.mean_s))}</td>"
            f"<td class='num'>{_esc(format_seconds(result.timing.stdev_s))}</td>"
            f"<td class='num'>{result.timing.repeats} × {result.timing.loops}</td>"
            f"<td class='num'>{_esc(_rate(result.timing.mean_s))}</td>"
            f"<td class='bar'><span style='width: {width:.1f}%'></span></td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


def _header_cells() -> list[str]:
    labels = (
        ("Module", ""),
        ("Function", ""),
        ("Best", "num"),
        ("Mean", "num"),
        ("Stdev", "num"),
        ("Repeats × loops", "num"),
        ("Calls/s", "num"),
        ("", ""),
    )
    return [f"<th class='{css}'>{label}</th>" if css else f"<th>{label}</th>" for label, css in labels]


def _profiles(report: Report) -> str:
    blocks: list[str] = []
    for result in report.results:
        if not result.profiled:
            continue
        summary = _profile_summary(result)
        blocks.append(f"<h3 id='{_anchor(result)}'>{_esc(result.module)}.{_esc(result.name)}</h3>")
        blocks.append(f"<p>{summary}</p>")
        blocks.append("<h4>Self time</h4>")
        blocks.append(_profile_table(result.profile_self, result.profile_total_s))
        blocks.append("<h4>Cumulative time</h4>")
        blocks.append(_profile_table(result.profile_cumulative, result.profile_total_s))
    return "\n".join(blocks)


def _profile_table(entries: tuple[ProfileEntry, ...], total_s: float) -> str:
    rows = [
        "<table>",
        "<thead><tr><th>Function</th><th>Location</th>"
        "<th class='num'>Calls</th><th class='num'>Self</th>"
        "<th class='num'>Cumulative</th><th class='num'>Self share</th></tr></thead>",
        "<tbody>",
    ]
    for entry in entries:
        rows.append(
            "<tr>"
            f"<td><code>{_esc(entry.function)}</code></td>"
            f"<td><code>{_esc(entry.location)}</code></td>"
            f"<td class='num'>{entry.calls:,}</td>"
            f"<td class='num'>{_esc(format_seconds(entry.tottime_s))}</td>"
            f"<td class='num'>{_esc(format_seconds(entry.cumtime_s))}</td>"
            f"<td class='num'>{_share(entry, total_s):.1f}%</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


def _skipped_table() -> str:
    return _pair_table(SKIPPED, "Code", "Why it is not timed")


def _pair_table(rows_in: tuple[tuple[str, str], ...], left: str, right: str) -> str:
    rows = [
        "<table>",
        f"<thead><tr><th>{_esc(left)}</th><th>{_esc(right)}</th></tr></thead>",
        "<tbody>",
    ]
    for name, reason in rows_in:
        rows.append(f"<tr><td><code>{_esc(name)}</code></td><td>{_esc(reason)}</td></tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def _finding(slowest: Result) -> str:
    callee = slowest.dominant_callee if slowest.profiled else None
    leaf = slowest.hottest if slowest.profiled else None
    if callee is not None:
        text = (
            f"Inside that profile, <code>{_esc(callee.function)}</code> "
            f"({_esc(callee.location)}) accounts for "
            f"{_portion(callee.cumtime_s, slowest.profile_total_s):.0f}% of the instrumented run."
        )
        if leaf is not None and leaf.function != callee.function:
            text += f" Most self time is in <code>{_esc(leaf.function)}</code>."
        return text
    if leaf is not None:
        return (
            f"Most self time in that profile is <code>{_esc(leaf.function)}</code> "
            f"({_esc(leaf.location)})."
        )
    return "That call was not profiled."


def _profile_summary(result: Result) -> str:
    callee = result.dominant_callee
    leaf = result.hottest
    if callee is not None:
        text = (
            f"Slow spot: <code>{_esc(callee.function)}</code> "
            f"({_esc(callee.location)}), {_esc(format_seconds(callee.cumtime_s))} cumulative, "
            f"{_portion(callee.cumtime_s, result.profile_total_s):.0f}% of this run."
        )
        if leaf is not None and leaf.function != callee.function:
            text += (
                f" Most self time is in <code>{_esc(leaf.function)}</code> "
                f"({_esc(format_seconds(leaf.tottime_s))})."
            )
        return text
    if leaf is None:
        return "No functions recorded."
    return (
        f"Slow spot: <code>{_esc(leaf.function)}</code> "
        f"({_esc(leaf.location)}), {_esc(format_seconds(leaf.tottime_s))} self, "
        f"{_share(leaf, result.profile_total_s):.0f}% of this run."
    )


def _anchor(result: Result) -> str:
    raw = f"{result.module}.{result.name}"
    return "".join(char if char.isalnum() else "-" for char in raw)


def _share(entry: ProfileEntry, total_s: float) -> float:
    return _portion(entry.tottime_s, total_s)


def _portion(part: float, total_s: float) -> float:
    if total_s <= 0:
        return 0.0
    return part / total_s * 100


def _rate(mean_s: float) -> str:
    if mean_s <= 0:
        return "0"
    rate = 1.0 / mean_s
    if rate >= 100:
        return f"{rate:,.0f}"
    if rate >= 1:
        return f"{rate:,.1f}"
    return f"{rate:.3f}"


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


_CSS = """
body { margin: 0 auto; max-width: 1080px; padding: 2rem 1.25rem 4rem;
  font-family: "Segoe UI", system-ui, sans-serif; color: #1c1917; background: #fafaf9; line-height: 1.45; }
h1 { font-size: 1.6rem; font-weight: 650; letter-spacing: -0.02em; margin-bottom: 0.4rem; }
h2 { font-size: 1.15rem; margin-bottom: 0.4rem; }
h3 { font-size: 1rem; margin-bottom: 0.2rem; }
h4 { font-size: 0.85rem; margin: 0.8rem 0 0.3rem; color: #57534e; }
a { color: #0f766e; }
table { width: 100%; border-collapse: collapse; font-size: 0.92rem; background: white; }
th, td { text-align: left; padding: 0.45rem 0.55rem; border-bottom: 1px solid #e7e5e4; vertical-align: top; }
th { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: #57534e; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.bar { width: 7.5rem; }
.bar span { display: block; height: 0.45rem; background: #0f766e; border-radius: 999px; }
.note { color: #57534e; font-size: 0.82rem; }
.badge { display: inline-block; padding: 0.05rem 0.4rem; border-radius: 999px;
  background: #fef3c7; color: #92400e; font-size: 0.72rem; }
.lead { background: white; border: 1px solid #e7e5e4; border-radius: 12px; padding: 0.2rem 1.1rem; }
section { margin-top: 2.25rem; }
code { font-family: ui-monospace, Consolas, monospace; font-size: 0.88em; }
"""
