"use client";

import { useEffect, useState, useTransition, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { PlayerFilters } from "@/lib/server/data";

const POS = ["", "GKP", "DEF", "MID", "FWD"];

function queryFor(filters: PlayerFilters) {
  const q = new URLSearchParams();
  if (filters.position) q.set("position", String(filters.position));
  q.set("max_cost", String(filters.maxCost));
  q.set("horizon", String(filters.horizon));
  return q.toString();
}

export function PlayersChrome({
  filters,
  children,
}: {
  filters: PlayerFilters;
  children: ReactNode;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [maxCost, setMaxCost] = useState(filters.maxCost);

  useEffect(() => {
    setMaxCost(filters.maxCost);
  }, [filters.maxCost]);

  useEffect(() => {
    if (maxCost === filters.maxCost) return;
    const timer = setTimeout(() => {
      startTransition(() => {
        router.push(`/players?${queryFor({ ...filters, maxCost })}`);
      });
    }, 250);
    return () => clearTimeout(timer);
  }, [maxCost, filters, router]);

  function push(next: PlayerFilters) {
    startTransition(() => {
      router.push(`/players?${queryFor(next)}`);
    });
  }

  return (
    <>
      <div className="flex flex-wrap gap-4 items-center py-4 border-y border-rule my-6">
        {[1, 2, 3, 4].map((p) => (
          <button
            key={p}
            type="button"
            className={`btn ${filters.position === p ? "btn-primary" : "btn-secondary"}`}
            onClick={() => push({ ...filters, position: filters.position === p ? undefined : p })}
          >
            {POS[p]}
          </button>
        ))}
        <label className="flex items-center gap-2">
          Max £{(maxCost / 10).toFixed(1)}m
          <input
            type="range"
            min={35}
            max={150}
            value={maxCost}
            onChange={(e) => setMaxCost(Number(e.target.value))}
          />
        </label>
        <label>
          Horizon{" "}
          <select
            value={filters.horizon}
            onChange={(e) => push({ ...filters, horizon: Number(e.target.value) })}
            className="bg-transparent border-b border-ink"
          >
            {[1, 2, 3, 4, 5, 6].map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className={pending ? "opacity-50" : undefined}>{children}</div>
    </>
  );
}
