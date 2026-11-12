"use client";

import { useState } from "react";
import type { PlayerRow } from "@/lib/api";
import { tabPanelId, tabTriggerId, Tabs, type TabOption } from "@/components/programme/Tabs";
import { MetricBar, PlayerCell } from "./StatTable";
import type { PositionId } from "./insights-view";

const LEADER_TABS: TabOption<string>[] = [
  { id: "1", label: "GKP" },
  { id: "2", label: "DEF" },
  { id: "3", label: "MID" },
  { id: "4", label: "FWD" },
];

const GROUP: Record<PositionId, string> = {
  1: "goalkeepers",
  2: "defenders",
  3: "midfielders",
  4: "strikers",
};

function LeaderList({ players, ownedIds }: { players: PlayerRow[]; ownedIds: number[] }) {
  if (players.length === 0) return <p className="insight-note">Nothing to show yet.</p>;
  const peak = players.reduce((max, player) => Math.max(max, player.proj), 0);
  return (
    <ol className="mt-1">
      {players.map((player, index) => (
        <li key={player.id} className="insight-line">
          <span className="insight-rank nums" aria-hidden>
            {index + 1}
          </span>
          <span className="min-w-0 flex-1 text-sm">
            <PlayerCell player={player} ownedIds={ownedIds} />
          </span>
          <MetricBar value={player.proj} max={peak} label={player.proj.toFixed(1)} />
        </li>
      ))}
    </ol>
  );
}

export function LeadersCard({
  leaders,
  ownedIds,
  position,
}: {
  leaders: Record<number, PlayerRow[]>;
  ownedIds: number[];
  position: PositionId | undefined;
}) {
  const [tab, setTab] = useState("3");
  const shown = position ?? Number(tab);
  const list = (
    <LeaderList players={leaders[shown] ?? []} ownedIds={ownedIds} />
  );

  return (
    <section className="insight-card">
      <div className="insight-card-head">
        <div>
          <p className="insight-title">{position == null ? "Projected points" : `Top ${GROUP[position]}`}</p>
          <p className="insight-note">Top five for the next gameweek.</p>
        </div>
        {position == null ? (
          <Tabs name="leaders" label="Position" tabs={LEADER_TABS} value={tab} onChange={setTab} />
        ) : null}
      </div>
      {position == null ? (
        <div role="tabpanel" id={tabPanelId("leaders")} aria-labelledby={tabTriggerId("leaders", tab)}>
          {list}
        </div>
      ) : (
        list
      )}
    </section>
  );
}
