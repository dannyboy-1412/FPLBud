import type { ReactNode } from "react";
import type { StatPlayer } from "@/lib/api";
import { POS } from "./format";

export function PlayerCell({ player, ownedIds = [] }: { player: StatPlayer; ownedIds?: number[] }) {
  const owned = ownedIds.includes(player.id);
  return (
    <>
      {player.web_name}
      {owned ? <span className="caption ml-1">you own</span> : null}{" "}
      <span className="caption">
        {player.team_short} · {POS[player.position_id]}
      </span>
    </>
  );
}

export function StatTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: { id: string | number; cells: ReactNode[] }[];
}) {
  if (rows.length === 0) {
    return <p className="caption">Nothing to show yet.</p>;
  }
  return (
    <table className="w-full text-sm nums">
      <thead>
        <tr className="kicker border-b border-ink text-left">
          {headers.map((header) => (
            <th key={header} className="py-2 pr-3 font-semibold">
              {header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={row.id} className={`h-11 ${i % 2 ? "bg-paper-deep" : ""}`}>
            {row.cells.map((cell, j) => (
              <td key={j} className="pr-3">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
