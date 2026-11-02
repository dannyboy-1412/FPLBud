import type { Citation } from "@/lib/chat";

export function PlayerChip({ citation }: { citation: Citation }) {
  const price = citation.price_m == null ? null : `£${citation.price_m.toFixed(1)}m`;
  return (
    <span className="chat-chip">
      <span className="chat-chip-name">{citation.name}</span>
      {citation.team ? <span className="chat-chip-team">{citation.team}</span> : null}
      {price ? <span className="chat-chip-price">{price}</span> : null}
    </span>
  );
}
