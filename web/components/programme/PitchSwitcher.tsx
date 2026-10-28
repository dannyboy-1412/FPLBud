"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent } from "react";
import { Pitch } from "@/components/programme/Pitch";
import { PitchSkeleton } from "@/components/programme/Skeletons";
import type { PublicTeam, SuggestedTransfers, SuggestedXi, TransferOption } from "@/lib/api";
import { fetchSuggestedTransfers, fetchSuggestedXi } from "@/lib/server/actions";

export type PitchLineup = "ready" | "locked";

type SquadPlayer = PublicTeam["squad_players"][number];
type PitchTab = "squad" | "suggested" | "transfers";

const TABS: PitchTab[] = ["squad", "suggested", "transfers"];

function freeTransferLine(count: number) {
  if (count === 1) return "You have 1 free transfer.";
  if (count === 0) return "You have no free transfer.";
  return `You have ${count} free transfers.`;
}

function optionKey(option: TransferOption) {
  const moves = option.moves.map((move) => `${move.out_id}-${move.in_id}`).join(",");
  return `${option.action}:${moves}`;
}

function optionTitle(option: TransferOption) {
  if (option.action === "roll" || option.moves.length === 0) return "Roll the free transfer";
  if (option.moves.length === 1) {
    return `Sell ${option.moves[0].out_name} for ${option.moves[0].in_name}`;
  }
  return option.moves.map((move) => `${move.out_name} for ${move.in_name}`).join(", ");
}

function PitchViewToggle({
  tab,
  locked,
  onSelect,
}: {
  tab: PitchTab;
  locked: boolean;
  onSelect: (tab: PitchTab) => void;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = TABS.indexOf(tab);
    if (event.key === "ArrowLeft" && index > 0) {
      event.preventDefault();
      const next = TABS[index - 1];
      onSelect(next);
      document.getElementById(`pitch-tab-${next}`)?.focus();
      return;
    }
    if (event.key === "ArrowRight" && index < TABS.length - 1 && !locked) {
      event.preventDefault();
      const next = TABS[index + 1];
      onSelect(next);
      document.getElementById(`pitch-tab-${next}`)?.focus();
    }
  }

  const thumb =
    tab === "transfers" ? " is-transfers" : tab === "suggested" ? " is-suggested" : "";

  return (
    <div className="pitch-toggle">
      <div role="tablist" aria-label="Pitch view" className="pitch-toggle-track" onKeyDown={onKeyDown}>
        <span aria-hidden className={`pitch-toggle-thumb${thumb}`} />
        <div className="pitch-toggle-options">
          <button
            type="button"
            role="tab"
            id="pitch-tab-squad"
            aria-selected={tab === "squad"}
            aria-controls="pitch-tab-panel"
            tabIndex={tab === "squad" ? 0 : -1}
            onClick={() => onSelect("squad")}
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
            onClick={() => onSelect("suggested")}
          >
            Suggested 11
          </button>
          <button
            type="button"
            role="tab"
            id="pitch-tab-transfers"
            aria-selected={tab === "transfers"}
            aria-controls="pitch-tab-panel"
            tabIndex={tab === "transfers" ? 0 : -1}
            disabled={locked}
            onClick={() => onSelect("transfers")}
          >
            Transfers
          </button>
        </div>
      </div>
    </div>
  );
}

function placeSquad(
  team: PublicTeam,
  starters: number[],
  bench: number[],
  captainId: number | null,
  viceId: number | null,
  extras: SquadPlayer[],
) {
  const byId = new Map(team.squad_players.map((player) => [player.element, player]));
  for (const player of extras) byId.set(player.element, player);
  const ids = [...starters, ...bench];
  if (new Set(ids).size !== 15 || ids.some((id) => !byId.has(id))) return null;
  const placed = (id: number, squadPosition: number): SquadPlayer | null => {
    const player = byId.get(id);
    if (!player) return null;
    return {
      ...player,
      squad_position: squadPosition,
      is_captain: id === captainId,
      is_vice_captain: id === viceId,
    };
  };
  const squad = [
    ...starters.map((id, index) => placed(id, index + 1)),
    ...bench.map((id, index) => placed(id, index + 12)),
  ].filter((player): player is SquadPlayer => player != null);
  if (squad.length !== 15) return null;
  return { ...team, squad_players: squad };
}

function applyLineup(team: PublicTeam, lineup: SuggestedXi): PublicTeam | null {
  return placeSquad(team, lineup.starters, lineup.bench, lineup.captain_id, lineup.vice_id, []);
}

function applyOption(team: PublicTeam, option: TransferOption): PublicTeam | null {
  if (option.action === "roll") return team;
  return placeSquad(team, option.starters, option.bench, option.captain_id, option.vice_id, option.incomings);
}

export function PitchSwitcher({ team, lineup }: { team: PublicTeam; lineup: PitchLineup }) {
  const [tab, setTab] = useState<PitchTab>("squad");
  const [xi, setXi] = useState<SuggestedXi | null>(null);
  const [advice, setAdvice] = useState<SuggestedTransfers | null>(null);
  const [pickedKey, setPickedKey] = useState<string | null>(null);
  const [pending, setPending] = useState<PitchTab | null>(null);
  const [xiError, setXiError] = useState<string | null>(null);
  const [transferError, setTransferError] = useState<string | null>(null);
  const loadingXi = useRef(false);
  const loadingTransfers = useRef(false);
  const locked = lineup === "locked";

  async function loadXi() {
    if (loadingXi.current) return;
    loadingXi.current = true;
    setTab("suggested");
    setPending("suggested");
    setXiError(null);
    try {
      const next = await fetchSuggestedXi();
      if ("error" in next) {
        setXiError(next.error);
        return;
      }
      if (!applyLineup(team, next.lineup)) {
        setXiError("This suggestion doesn't match the squad on screen. Refresh the page.");
        return;
      }
      setXi(next.lineup);
    } finally {
      loadingXi.current = false;
      setPending((current) => (current === "suggested" ? null : current));
    }
  }

  async function loadTransfers() {
    if (loadingTransfers.current) return;
    loadingTransfers.current = true;
    setTab("transfers");
    setPending("transfers");
    setTransferError(null);
    try {
      const next = await fetchSuggestedTransfers();
      if ("error" in next) {
        setTransferError(next.error);
        return;
      }
      const options = next.advice.options ?? [];
      const viewable = options.length === 0 || options.some((option) => applyOption(team, option));
      if (!viewable) {
        setTransferError("This suggestion doesn't match the squad on screen. Refresh the page.");
        return;
      }
      const picked = options.find((option) => option.chosen) ?? options[0];
      setPickedKey(picked ? optionKey(picked) : null);
      setAdvice(next.advice);
    } finally {
      loadingTransfers.current = false;
      setPending((current) => (current === "transfers" ? null : current));
    }
  }

  function showSuggested() {
    if (locked) return;
    setTab("suggested");
    if (xi || xiError || loadingXi.current) return;
    void loadXi();
  }

  function showTransfers() {
    if (locked) return;
    setTab("transfers");
    if (advice || transferError || loadingTransfers.current) return;
    void loadTransfers();
  }

  function onSelect(next: PitchTab) {
    if (next === "squad") setTab("squad");
    if (next === "suggested") showSuggested();
    if (next === "transfers") showTransfers();
  }

  const shownXi = xi ? applyLineup(team, xi) : null;
  const transferOptions = [...(advice?.options ?? [])].sort((a, b) => b.recommended_pct - a.recommended_pct);
  const selectedOption =
    transferOptions.find((option) => optionKey(option) === pickedKey) ??
    transferOptions.find((option) => option.chosen) ??
    transferOptions[0];
  const shownTransfers = selectedOption ? (applyOption(team, selectedOption) ?? team) : null;
  const incomingIds = selectedOption?.moves.map((move) => move.in_id) ?? [];

  return (
    <div>
      {locked ? (
        <p className="caption mb-4">
          <Link href="/login" className="underline">
            Sign in
          </Link>{" "}
          to see a suggested starting XI and a transfer plan.
        </p>
      ) : null}
      {tab === "suggested" && pending === "suggested" ? (
        <p className="caption mb-4" role="status" aria-live="polite">
          Checking team news…
        </p>
      ) : null}
      {tab === "transfers" && pending === "transfers" ? (
        <p className="caption mb-4" role="status" aria-live="polite">
          Checking team news…
        </p>
      ) : null}
      {tab === "suggested" && xiError ? (
        <p className="caption mb-4">
          {xiError}{" "}
          <button type="button" className="btn-text" onClick={() => void loadXi()}>
            Try again
          </button>
        </p>
      ) : null}
      {tab === "transfers" && transferError ? (
        <p className="caption mb-4">
          {transferError}{" "}
          <button type="button" className="btn-text" onClick={() => void loadTransfers()}>
            Try again
          </button>
        </p>
      ) : null}
      {tab === "suggested" && shownXi ? <p className="caption mb-4">{xi?.summary}</p> : null}
      {tab === "transfers" && advice && transferOptions.length > 0 ? (
        <div className="transfer-board mb-4">
          <p className="kicker">Transfer suggestions</p>
          <p className="mt-1 text-sm">{freeTransferLine(advice.free_transfers)}</p>
          <div className="transfer-options mt-3" role="list">
            {transferOptions.map((option) => {
              const key = optionKey(option);
              const viewing = selectedOption ? optionKey(selectedOption) === key : false;
              return (
                <button
                  key={key}
                  type="button"
                  className={`transfer-option${option.chosen ? " is-recommended" : ""}${viewing ? " is-viewing" : ""}`}
                  aria-pressed={viewing}
                  onClick={() => setPickedKey(key)}
                >
                  <span className="transfer-pct">
                    <span className="transfer-pct-value">{option.recommended_pct}</span>
                    <span className="transfer-pct-mark">%</span>
                    <span className="transfer-pct-label">{option.chosen ? "Recommended" : "Suggested"}</span>
                  </span>
                  <span className="transfer-copy">
                    <span className="transfer-title">{optionTitle(option)}</span>
                    <span className="transfer-reason">{option.reason}</span>
                    <span className="transfer-meter" aria-hidden>
                      <span style={{ width: `${option.recommended_pct}%` }} />
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
      <div className="pitch-frame">
        <PitchViewToggle tab={tab} locked={locked} onSelect={onSelect} />
        <div
          id="pitch-tab-panel"
          role="tabpanel"
          aria-labelledby={
            tab === "squad" ? "pitch-tab-squad" : tab === "suggested" ? "pitch-tab-suggested" : "pitch-tab-transfers"
          }
        >
          {tab === "squad" ? <Pitch team={team} /> : null}
          {tab === "suggested" && pending === "suggested" ? <PitchSkeleton /> : null}
          {tab === "suggested" && shownXi ? <Pitch team={shownXi} /> : null}
          {tab === "transfers" && pending === "transfers" ? <PitchSkeleton /> : null}
          {tab === "transfers" && shownTransfers ? (
            <Pitch team={shownTransfers} incomingIds={incomingIds} />
          ) : null}
        </div>
      </div>
    </div>
  );
}
