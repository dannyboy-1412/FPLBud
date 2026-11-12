import type { AttentionRow } from "@/lib/api";
import { PlayerCell } from "./StatTable";

export function AttentionList({
  players,
  empty,
  ownedIds = [],
  limit,
}: {
  players: AttentionRow[] | undefined;
  empty: string;
  ownedIds?: number[];
  limit?: number;
}) {
  const rows = players ?? [];
  if (rows.length === 0) return <p className="insight-note">{empty}</p>;
  const shown = limit == null ? rows : rows.slice(0, limit);
  return (
    <ul className="attention-list">
      {shown.map((player) => (
        <li key={player.id} className="attention-row">
          <p className="attention-name">
            <PlayerCell player={player} ownedIds={ownedIds} />
          </p>
          {player.detail ? <p className="attention-detail">{player.detail}</p> : null}
          {player.run ? <p className="attention-run">{player.run}</p> : null}
        </li>
      ))}
    </ul>
  );
}
