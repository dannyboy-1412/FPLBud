import type { Citation } from "@/lib/chat";

export function PlayerChip({ citation }: { citation: Citation }) {
  const price = citation.price_m == null ? null : `£${citation.price_m.toFixed(1)}m`;
  return (
    <span className="inline-flex items-baseline gap-1 border border-rule px-1 align-baseline">
      <span>{citation.name}</span>
      {citation.team ? <span className="text-ink-soft">{citation.team}</span> : null}
      {price ? <span>{price}</span> : null}
    </span>
  );
}
