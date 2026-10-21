"use client";

import { useState } from "react";
import { api, type PlayerRow } from "@/lib/api";

const POS = ["", "GKP", "DEF", "MID", "FWD"];

export function PlayersRows({ rows }: { rows: PlayerRow[] }) {
  const [open, setOpen] = useState<Record<string, unknown> | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);

  return (
    <>
      <table className="w-full text-sm nums">
        <thead>
          <tr className="kicker border-b border-ink text-left">
            <th className="py-2">#</th>
            <th>Player</th>
            <th>Price</th>
            <th>Proj</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.id}
              className={`h-11 cursor-pointer ${i % 2 ? "bg-paper-deep" : ""} ${loadingId === r.id ? "opacity-50" : ""}`}
              onClick={async () => {
                setLoadingId(r.id);
                try {
                  setOpen(await api(`/players/${r.id}`));
                } finally {
                  setLoadingId(null);
                }
              }}
            >
              <td>{r.rank}</td>
              <td>
                {r.web_name}{" "}
                <span className="caption">
                  {r.team_short} · {POS[r.position_id]}
                </span>
              </td>
              <td>£{(r.now_cost / 10).toFixed(1)}m</td>
              <td className="font-[family-name:var(--font-fraunces)] font-semibold">{r.proj.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {open ? (
        <div className="fixed inset-y-0 right-0 w-[520px] max-w-full bg-paper-bright border-l border-ink p-8 overflow-auto">
          <button type="button" className="btn btn-text" onClick={() => setOpen(null)}>
            Close
          </button>
          <pre className="caption whitespace-pre-wrap mt-4">{JSON.stringify(open, null, 2)}</pre>
        </div>
      ) : null}
    </>
  );
}
