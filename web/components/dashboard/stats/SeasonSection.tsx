import { getMySeason } from "@/lib/server/data";
import { pounds, rankLabel, signed } from "./format";
import { RankSparkline } from "./RankSparkline";
import { StatTable } from "./StatTable";

const CHIP_LABEL: Record<string, string> = {
  wildcard: "WC",
  freehit: "FH",
  bboost: "BB",
  "3xc": "TC",
};

export async function SeasonSection() {
  const data = await getMySeason();
  const { summary } = data;
  return (
    <div className="space-y-10">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        <div className="border-b border-rule pb-3">
          <p className="kicker">Total points</p>
          <p className="stat mt-2">{summary.total_points}</p>
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Overall rank</p>
          <p className="stat mt-2">{rankLabel(summary.latest_overall_rank)}</p>
          {summary.latest_percentile != null ? (
            <p className="caption">Top {summary.latest_percentile}%</p>
          ) : null}
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Best GW</p>
          <p className="stat mt-2">{summary.best_gw ? summary.best_gw.points : "—"}</p>
          {summary.best_gw ? <p className="caption">GW{summary.best_gw.event}</p> : null}
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Worst GW</p>
          <p className="stat mt-2">{summary.worst_gw ? summary.worst_gw.points : "—"}</p>
          {summary.worst_gw ? <p className="caption">GW{summary.worst_gw.event}</p> : null}
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Above average</p>
          <p className="stat mt-2">{summary.gws_above_average}</p>
          <p className="caption">gameweeks</p>
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Left on bench</p>
          <p className="stat mt-2">{summary.bench_points_total}</p>
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Hits taken</p>
          <p className="stat mt-2">−{summary.hit_cost_total}</p>
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Captain vs crowd</p>
          <p className="stat mt-2">
            {data.captain_returns.total}
            <span className="caption ml-2">vs {data.captain_returns.crowd_total}</span>
          </p>
        </div>
      </div>
      <RankSparkline rows={data.rows} />
      <section>
        <p className="kicker mb-3">Gameweeks</p>
        <StatTable
          headers={["GW", "Pts", "vs avg", "Rank", "OR", "Bench", "Hits", "Value", "Chip"]}
          rows={data.rows.map((row) => ({
            id: row.event,
            cells: [
              row.event,
              row.points,
              row.delta_vs_avg == null ? "—" : signed(row.delta_vs_avg, 0),
              rankLabel(row.rank),
              rankLabel(row.overall_rank),
              row.points_on_bench,
              row.hit_cost ? `−${row.hit_cost}` : "0",
              pounds(row.value),
              row.chip ? (CHIP_LABEL[row.chip] ?? row.chip) : "—",
            ],
          }))}
        />
      </section>
      <section>
        <p className="kicker mb-3">Captain returns</p>
        <p className="caption mb-3">Your captain&apos;s points (with the multiplier) against the crowd&apos;s most-captained player at ×2.</p>
        <StatTable
          headers={["GW", "Your C", "Pts", "Crowd", "Pts", "Δ"]}
          rows={data.captain_returns.rows.map((row) => ({
            id: row.event,
            cells: [
              row.event,
              `${row.captain_name}${row.multiplier === 3 ? " (TC)" : ""}`,
              row.points,
              row.crowd_name ?? "—",
              row.crowd_points,
              signed(row.delta, 0),
            ],
          }))}
        />
      </section>
    </div>
  );
}
