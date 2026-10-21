"""Tune (a, b) by OLS of actual points on S once enough GWs exist."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fplcore" / "src"))

from fplcore.db import connect  # noqa: E402


def main() -> None:
    with connect() as conn:
        rows = list(
            conn.execute(
                """
                select m.form_score, m.fixture_score, m.home_score, m.xgi_score,
                       p.position_id, s.total_points
                  from player_metrics m
                  join players p on p.season_id = m.season_id and p.id = m.player_id
                  join player_gameweek_stats s
                    on s.season_id = m.season_id and s.player_id = m.player_id and s.round = m.computed_for_gw
                 where m.horizon = 1
                """
            )
        )
    if len(rows) < 200:
        print("not enough stored metrics yet; using fallback a=1, b=6")
        return
    by_pos: dict[int, list[tuple[float, float]]] = {}
    for row in rows:
        s = (
            0.30 * float(row["form_score"] or 0)
            + 0.25 * float(row["fixture_score"] or 0)
            + 0.10 * float(row["home_score"] or 0)
            + 0.35 * float(row["xgi_score"] or 0)
        )
        by_pos.setdefault(int(row["position_id"]), []).append((s, float(row["total_points"])))
    for pos, pairs in sorted(by_pos.items()):
        x = np.array([p[0] for p in pairs])
        y = np.array([p[1] for p in pairs])
        a, b = np.polyfit(x, y, 1)[1], np.polyfit(x, y, 1)[0]
        # polyfit returns [b, a] for y = b x + a
        coeffs = np.polyfit(x, y, 1)
        b, a = float(coeffs[0]), float(coeffs[1])
        print(f"position {pos}: a={a:.3f} b={b:.3f} n={len(pairs)}")


if __name__ == "__main__":
    main()
