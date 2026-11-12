"use client";

import { useState } from "react";
import type { AttentionRow } from "@/lib/api";
import { tabPanelId, tabTriggerId, Tabs } from "@/components/programme/Tabs";
import { AttentionList } from "./AttentionList";
import {
  defaultScope,
  matchingPosition,
  PREVIEW_ROWS,
  type AttentionScope,
  type PositionId,
} from "./insights-view";

const SCOPES: { id: AttentionScope; label: string }[] = [
  { id: "squad", label: "Your squad" },
  { id: "league", label: "League" },
];

function Column({
  title,
  tone,
  caption,
  players,
  empty,
  ownedIds,
  open,
  onToggle,
}: {
  title: string;
  tone: "act" | "calm";
  caption: string;
  players: AttentionRow[] | undefined;
  empty: string;
  ownedIds: number[];
  open: boolean;
  onToggle: () => void;
}) {
  const total = players?.length ?? 0;
  return (
    <div className="finish-pane">
      <p className="finish-label">
        <span className={`series-dot is-${tone}`} aria-hidden />
        {title}
      </p>
      <p className="insight-note mb-2">{caption}</p>
      <AttentionList
        players={players}
        empty={empty}
        ownedIds={ownedIds}
        limit={open ? undefined : PREVIEW_ROWS}
      />
      {total > PREVIEW_ROWS ? (
        <button type="button" className="insight-more" aria-expanded={open} onClick={onToggle}>
          {open ? "Show less" : "Show all"}
        </button>
      ) : null}
    </div>
  );
}

export function AttentionPanel({
  hasTeam,
  squadSort,
  squadKeep,
  leagueEasy,
  leagueHard,
  ownedIds,
  position,
}: {
  hasTeam: boolean;
  squadSort: AttentionRow[] | undefined;
  squadKeep: AttentionRow[] | undefined;
  leagueEasy: AttentionRow[];
  leagueHard: AttentionRow[];
  ownedIds: number[];
  position: PositionId | undefined;
}) {
  const [scope, setScope] = useState<AttentionScope>(() => defaultScope(hasTeam));
  const [openAct, setOpenAct] = useState(false);
  const [openCalm, setOpenCalm] = useState(false);
  const squad = scope === "squad";
  const act = matchingPosition(squad ? squadSort : leagueHard, position);
  const calm = matchingPosition(squad ? squadKeep : leagueEasy, position);

  function chooseScope(next: AttentionScope) {
    setScope(next);
    setOpenAct(false);
    setOpenCalm(false);
  }

  return (
    <section className="insight-card">
      <div className="insight-card-head">
        <div>
          <p className="insight-title">{squad ? "Your squad" : "Fixture runs"}</p>
          <p className="insight-note">
            {squad
              ? "Who to deal with before the deadline, and who can stay."
              : "The easiest and hardest next three among players who are playing."}
          </p>
        </div>
        <Tabs name="attention" label="Squad or league" tabs={SCOPES} value={scope} onChange={chooseScope} />
      </div>
      <div role="tabpanel" id={tabPanelId("attention")} aria-labelledby={tabTriggerId("attention", scope)}>
      {squad && !hasTeam ? (
        <p className="insight-note">Import a team to see who needs a decision.</p>
      ) : (
        <div className="finish-grid">
          {squad ? (
            <Column
              title="Sort out"
              tone="act"
              caption="A flag, too few starts, or a hard next three."
              players={act}
              empty="Nobody in the squad needs a look this week."
              ownedIds={[]}
              open={openAct}
              onToggle={() => setOpenAct((open) => !open)}
            />
          ) : (
            <Column
              title="Easy run"
              tone="calm"
              caption="An easy next three. A place to look for a transfer."
              players={calm}
              empty="Nobody who is playing has a clearly easy next three."
              ownedIds={ownedIds}
              open={openCalm}
              onToggle={() => setOpenCalm((open) => !open)}
            />
          )}
          {squad ? (
            <Column
              title="Leave alone"
              tone="calm"
              caption="No flag, starting most weeks, and an easy next three."
              players={calm}
              empty="Nobody in the squad is secure through an easy run."
              ownedIds={[]}
              open={openCalm}
              onToggle={() => setOpenCalm((open) => !open)}
            />
          ) : (
            <Column
              title="Hard run"
              tone="act"
              caption="A hard next three. Leave them until the run turns."
              players={act}
              empty="Nobody who is playing has a clearly hard next three."
              ownedIds={ownedIds}
              open={openAct}
              onToggle={() => setOpenAct((open) => !open)}
            />
          )}
        </div>
      )}
      </div>
    </section>
  );
}
