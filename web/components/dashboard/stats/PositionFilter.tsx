"use client";

import Link from "next/link";
import { useLinkStatus } from "next/link";
import { insightsHref, type BoardId, type PositionId } from "./insights-view";

const LINKS: { position: PositionId | undefined; label: string; name: string }[] = [
  { position: undefined, label: "All", name: "All positions" },
  { position: 1, label: "GKP", name: "Goalkeepers" },
  { position: 2, label: "DEF", name: "Defenders" },
  { position: 3, label: "MID", name: "Midfielders" },
  { position: 4, label: "FWD", name: "Strikers" },
];

function PendingDot() {
  const { pending } = useLinkStatus();
  return (
    <span className="insight-pending" aria-hidden>
      <span className={pending ? "is-on" : undefined} />
    </span>
  );
}

export function PositionFilter({ position, board }: { position: PositionId | undefined; board: BoardId }) {
  return (
    <nav aria-label="Position" className="insight-segments">
      {LINKS.map((item) => {
        const active = item.position === position;
        return (
          <Link
            key={item.label}
            href={insightsHref(item.position, board)}
            scroll={false}
            aria-current={active ? "page" : undefined}
            aria-label={item.name}
          >
            {item.label}
            <PendingDot />
          </Link>
        );
      })}
    </nav>
  );
}
