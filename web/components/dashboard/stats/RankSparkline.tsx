import type { SeasonGwRow } from "@/lib/api";
import { rankLabel } from "./format";

function polyline(values: number[], width: number, height: number, pad: number, invert: boolean) {
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  return values
    .map((value, i) => {
      const x = pad + (i * (width - 2 * pad)) / (values.length - 1);
      const t = (value - min) / span;
      const y = invert ? pad + t * (height - 2 * pad) : height - pad - t * (height - 2 * pad);
      return `${x},${y}`;
    })
    .join(" ");
}

export function RankSparkline({ rows }: { rows: SeasonGwRow[] }) {
  const ranks = rows.filter((row) => row.overall_rank != null);
  if (ranks.length < 2) return null;
  const width = 640;
  const height = 120;
  const pad = 10;
  const points = polyline(
    ranks.map((row) => row.overall_rank as number),
    width,
    height,
    pad,
    true,
  );
  const first = ranks[0].overall_rank;
  const last = ranks[ranks.length - 1].overall_rank;
  return (
    <div>
      <p className="kicker mb-3">Overall rank</p>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full max-w-xl h-28"
        role="img"
        aria-label={`Overall rank from ${rankLabel(first)} to ${rankLabel(last)}`}
      >
        <polyline fill="none" stroke="var(--vermilion)" strokeWidth="2.5" points={points} />
      </svg>
      <p className="caption">
        GW{ranks[0].event}: {rankLabel(first)} → GW{ranks[ranks.length - 1].event}: {rankLabel(last)}
      </p>
    </div>
  );
}
