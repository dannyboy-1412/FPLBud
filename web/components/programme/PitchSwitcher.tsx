"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent } from "react";
import { Pitch } from "@/components/programme/Pitch";
import { PitchSkeleton } from "@/components/programme/Skeletons";
import type { PublicTeam, SuggestedXi } from "@/lib/api";
import { fetchSuggestedXi } from "@/lib/server/actions";

export type PitchLineup = "ready" | "locked";

type SquadPlayer = PublicTeam["squad_players"][number];

function PitchViewToggle({
  tab,
  locked,
  onSquad,
  onSuggested,
}: {
  tab: "squad" | "suggested";
  locked: boolean;
  onSquad: () => void;
  onSuggested: () => void;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      onSquad();
      document.getElementById("pitch-tab-squad")?.focus();
      return;
    }
    if (event.key === "ArrowRight" && !locked) {
      event.preventDefault();
      onSuggested();
      document.getElementById("pitch-tab-suggested")?.focus();
    }
  }

  return (
    <div className="pitch-toggle">
      <div role="tablist" aria-label="Pitch view" className="pitch-toggle-track" onKeyDown={onKeyDown}>
        <span aria-hidden className={`pitch-toggle-thumb${tab === "suggested" ? " is-suggested" : ""}`} />
        <div className="pitch-toggle-options">
          <button
            type="button"
            role="tab"
            id="pitch-tab-squad"
            aria-selected={tab === "squad"}
            aria-controls="pitch-tab-panel"
            tabIndex={tab === "squad" ? 0 : -1}
            onClick={onSquad}
          >
            Your squad
          </button>
          <button
            type="button"
            role="tab"
            id="pitch-tab-suggested"
            aria-selected={tab === "suggested"}
            aria-controls="pitch-tab-panel"
            tabIndex={tab === "suggested" ? 0 : -1}
            disabled={locked}
            onClick={onSuggested}
          >
            Suggested 11
          </button>
        </div>
      </div>
    </div>
  );
}

function applyLineup(team: PublicTeam, lineup: SuggestedXi): PublicTeam | null {
  const byId = new Map(team.squad_players.map((player) => [player.element, player]));
  const ids = [...lineup.starters, ...lineup.bench];
  if (new Set(ids).size !== 15 || ids.some((id) => !byId.has(id))) return null;
  const placed = (id: number, squadPosition: number, captain: boolean, vice: boolean): SquadPlayer | null => {
    const player = byId.get(id);
    if (!player) return null;
    return {
      ...player,
      squad_position: squadPosition,
      is_captain: captain,
      is_vice_captain: vice,
    };
  };
  const starters = lineup.starters.map((id, index) =>
    placed(id, index + 1, id === lineup.captain_id, id === lineup.vice_id),
  );
  const bench = lineup.bench.map((id, index) => placed(id, index + 12, false, false));
  const squad = [...starters, ...bench].filter((player): player is SquadPlayer => player != null);
  if (squad.length !== 15) return null;
  return { ...team, squad_players: squad };
}

export function PitchSwitcher({ team, lineup }: { team: PublicTeam; lineup: PitchLineup }) {
  const [tab, setTab] = useState<"squad" | "suggested">("squad");
  const [result, setResult] = useState<SuggestedXi | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loading = useRef(false);

  async function load() {
    if (loading.current) return;
    loading.current = true;
    setTab("suggested");
    setPending(true);
    setError(null);
    try {
      const next = await fetchSuggestedXi();
      if ("error" in next) {
        setError(next.error);
        return;
      }
      if (!applyLineup(team, next.lineup)) {
        setError("This suggestion doesn't match the squad on screen. Refresh the page.");
        return;
      }
      setResult(next.lineup);
    } finally {
      loading.current = false;
      setPending(false);
    }
  }

  function showSuggested() {
    setTab("suggested");
    if (result || error || loading.current) return;
    void load();
  }

  const shown = result ? applyLineup(team, result) : null;
  const locked = lineup === "locked";

  return (
    <div>
      {locked ? (
        <p className="caption mb-4">
          <Link href="/login" className="underline">
            Sign in
          </Link>{" "}
          to see a suggested starting XI.
        </p>
      ) : null}
      {tab === "suggested" && pending ? (
        <p className="caption mb-4" role="status" aria-live="polite">
          Checking team news…
        </p>
      ) : null}
      {tab === "suggested" && error ? (
        <p className="caption mb-4">
          {error}{" "}
          <button type="button" className="btn-text" onClick={() => void load()}>
            Try again
          </button>
        </p>
      ) : null}
      {tab === "suggested" && shown ? <p className="caption mb-4">{result?.summary}</p> : null}
      <div className="pitch-frame">
        <PitchViewToggle
          tab={tab}
          locked={locked}
          onSquad={() => setTab("squad")}
          onSuggested={showSuggested}
        />
        <div
          id="pitch-tab-panel"
          role="tabpanel"
          aria-labelledby={tab === "squad" ? "pitch-tab-squad" : "pitch-tab-suggested"}
        >
          {tab === "squad" ? <Pitch team={team} /> : null}
          {tab === "suggested" && pending ? <PitchSkeleton /> : null}
          {tab === "suggested" && shown ? <Pitch team={shown} /> : null}
        </div>
      </div>
    </div>
  );
}
