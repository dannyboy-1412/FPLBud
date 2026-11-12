"use client";

import { useState } from "react";
import type { AttentionRow, InsightsStats, PlayerRow } from "@/lib/api";
import { AttentionPanel } from "./AttentionPanel";
import { InsightsBoards } from "./InsightsBoards";
import { insightsHref, type BoardId, type PositionId } from "./insights-view";
import { LeadersCard } from "./LeadersCard";
import { PositionFilter } from "./PositionFilter";

export function InsightsView({
  position,
  board: initialBoard,
  hasTeam,
  squadSort,
  squadKeep,
  leaders,
  insights,
  ownedIds,
}: {
  position: PositionId | undefined;
  board: BoardId;
  hasTeam: boolean;
  squadSort: AttentionRow[] | undefined;
  squadKeep: AttentionRow[] | undefined;
  leaders: Record<number, PlayerRow[]>;
  insights: InsightsStats;
  ownedIds: number[];
}) {
  const [board, setBoard] = useState(initialBoard);

  function chooseBoard(next: BoardId) {
    setBoard(next);
    window.history.replaceState(null, "", insightsHref(position, next));
  }

  return (
    <div className="insights">
      <PositionFilter position={position} board={board} />
      <AttentionPanel
        hasTeam={hasTeam}
        squadSort={squadSort}
        squadKeep={squadKeep}
        leagueEasy={insights.easy_runs}
        leagueHard={insights.hard_runs}
        ownedIds={ownedIds}
        position={position}
      />
      <div className="insight-split">
        <LeadersCard leaders={leaders} ownedIds={ownedIds} position={position} />
        <InsightsBoards insights={insights} ownedIds={ownedIds} position={position} board={board} onBoard={chooseBoard} />
      </div>
    </div>
  );
}
