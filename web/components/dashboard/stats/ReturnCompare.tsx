import type { VarianceRow } from "@/lib/api";
import { PlayerCell } from "./StatTable";

const CLEAR_RETURN_GAP = 0.5;

function notableReturns(players: VarianceRow[] | undefined, direction: "short" | "ahead") {
  return (players ?? []).filter((player) =>
    direction === "short" ? player.xgi_delta >= CLEAR_RETURN_GAP : player.xgi_delta <= -CLEAR_RETURN_GAP,
  );
}

function returnsPhrase(goals: number, assists: number) {
  if (goals + assists === 0) return "No goals or assists yet";
  const parts: string[] = [];
  if (goals === 1) parts.push("1 goal");
  else if (goals > 1) parts.push(`${goals} goals`);
  if (assists === 1) parts.push("1 assist");
  else if (assists > 1) parts.push(`${assists} assists`);
  return parts.join(", ");
}

function ShareBar({ value, max }: { value: number; max: number }) {
  const width = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <span className="block h-1.5 bg-paper-deep" aria-hidden>
      <span className="block h-full bg-ink" style={{ width: `${width}%` }} />
    </span>
  );
}

export function ReturnCompare({
  players,
  direction,
  empty,
  ownedIds = [],
}: {
  players: VarianceRow[] | undefined;
  direction: "short" | "ahead";
  empty: string;
  ownedIds?: number[];
}) {
  const rows = notableReturns(players, direction);
  if (rows.length === 0) {
    return <p className="caption">{empty}</p>;
  }
  return (
    <ul className="border-t border-ink">
      {rows.map((player) => {
        const actual = player.goals + player.assists;
        const scale = Math.max(player.xgi, actual, 0.1);
        const gap = Math.abs(player.xgi_delta).toFixed(1);
        return (
          <li key={player.id} className="py-3 border-b border-rule">
            <div className="flex items-baseline justify-between gap-4">
              <span className="min-w-0">
                <PlayerCell player={player} ownedIds={ownedIds} />
              </span>
              <span className="shrink-0 text-sm font-semibold nums">
                {direction === "short" ? `Short by ${gap}` : `Ahead by ${gap}`}
              </span>
            </div>
            <div className="mt-2 space-y-1.5">
              <div className="grid grid-cols-[6.25rem_1fr_2.25rem] items-center gap-x-3 text-sm">
                <span className="text-ink-soft">Should have</span>
                <ShareBar value={player.xgi} max={scale} />
                <span className="nums text-right">{player.xgi.toFixed(1)}</span>
              </div>
              <div className="grid grid-cols-[6.25rem_1fr_2.25rem] items-center gap-x-3 text-sm">
                <span className="text-ink-soft">Has</span>
                <ShareBar value={actual} max={scale} />
                <span className="nums text-right">{actual}</span>
              </div>
            </div>
            <p className="caption mt-1.5">{returnsPhrase(player.goals, player.assists)}</p>
          </li>
        );
      })}
    </ul>
  );
}
