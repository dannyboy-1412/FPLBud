from types import SimpleNamespace

from fplcore.constants import (
    AGENT_RUN_KEEP_HOURS,
    ENTRY_CACHE_PRUNE_SECONDS,
    LOG_RETENTION_DAYS,
    MATCH_STATS_RETENTION_ROUNDS,
    METRIC_FORWARD_GWS,
)
from fplcore.db.repos import prune_retention, retention_windows, round_points_from_history


def test_retention_windows_keep_recent_rounds() -> None:
    windows = retention_windows(20)
    assert windows.stats_min_round == 20 - MATCH_STATS_RETENTION_ROUNDS
    assert windows.metrics_min_gw == 20
    assert windows.metrics_max_gw == 20 + METRIC_FORWARD_GWS - 1
    assert windows.stats_min_round == 12
    assert windows.metrics_max_gw == 25


def test_round_points_sums_double_gameweeks() -> None:
    history = [
        SimpleNamespace(round=6, total_points=2),
        SimpleNamespace(round=6, total_points=3),
        SimpleNamespace(round=7, total_points=8),
    ]
    assert sorted(round_points_from_history(history)) == [(6, 5), (7, 8)]


class _Result:
    def __init__(self, rows: list[dict] | None = None, rowcount: int = 0) -> None:
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, next_gw: int = 20) -> None:
        self.next_gw = next_gw
        self.statements: list[tuple[str, list | None]] = []

    def execute(self, sql: str, params: list | None = None) -> _Result:
        self.statements.append((sql, list(params) if params is not None else None))
        compact = " ".join(sql.split())
        if "from gameweeks" in compact and "is_next" in compact:
            return _Result([{"id": self.next_gw}])
        return _Result(rowcount=1)

    def deletes(self) -> list[tuple[str, list | None]]:
        found = []
        for sql, params in self.statements:
            compact = " ".join(sql.split()).lower()
            if compact.startswith("delete from"):
                table = compact.split()[2]
                found.append((table, params))
        return found


def test_prune_drops_rows_outside_windows() -> None:
    conn = _FakeConn(20)
    counts = prune_retention(conn)
    deletes = dict(conn.deletes())

    assert deletes["player_gameweek_stats"] == [12]
    assert deletes["player_metrics"] == [20, 25]
    assert deletes["suggested_lineups"] == [20]
    assert deletes["entry_cache"] == [ENTRY_CACHE_PRUNE_SECONDS]
    assert deletes["agent_runs"] == [AGENT_RUN_KEEP_HOURS]
    assert deletes["data_versions"] == [LOG_RETENTION_DAYS]
    assert deletes["ingest_runs"] == [LOG_RETENTION_DAYS]
    assert "team_snapshots" in deletes
    assert counts["player_gameweek_stats"] == 1
    agent_sql = next(sql for sql, _ in conn.statements if "delete from agent_runs" in " ".join(sql.split()).lower())
    assert "queued" in agent_sql
    assert "succeeded" in agent_sql
