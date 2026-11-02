"use client";

import { useState } from "react";
import { confirmChatMemory } from "@/lib/server/actions";

export function ProposalCard({
  proposal,
}: {
  proposal: { id: number; key: string; value: string; label: string };
}) {
  const [state, setState] = useState<"open" | "saved" | "dismissed">("open");
  const [error, setError] = useState<string | null>(null);

  if (state !== "open") {
    return <p className="caption">{state === "saved" ? "Filed with your preferences." : "Left off the file."}</p>;
  }

  return (
    <div className="chat-proposal" role="region" aria-label="Save a preference">
      <p className="kicker">Note for your file</p>
      <p className="chat-proposal-copy">
        Save {proposal.label}: {proposal.value}
      </p>
      <div className="chat-proposal-actions">
        <button type="button" className="chat-retry" onClick={() => void decide(true)}>
          Save
        </button>
        <button type="button" className="chat-quiet" onClick={() => void decide(false)}>
          Not now
        </button>
      </div>
      {error ? (
        <p className="text-vermilion-ink" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );

  async function decide(accept: boolean) {
    const result = await confirmChatMemory(proposal.id, accept);
    if (result.error) {
      setError(result.error);
      return;
    }
    setState(accept ? "saved" : "dismissed");
  }
}
