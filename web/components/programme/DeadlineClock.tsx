"use client";

import { useEffect, useState } from "react";

function countdown(iso: string) {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "Deadline passed";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d}d ${h % 24}h ${m}m`;
  return `${h}h ${m}m`;
}

export function DeadlineClock({ iso }: { iso: string }) {
  const [clock, setClock] = useState("");
  const [warn, setWarn] = useState(false);
  useEffect(() => {
    const tick = () => {
      setClock(countdown(iso));
      setWarn(new Date(iso).getTime() - Date.now() < 86_400_000);
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [iso]);
  if (!clock) return null;
  return <span className={`block mt-1.5 nums ${warn ? "text-vermilion-ink" : ""}`}>{clock}</span>;
}
