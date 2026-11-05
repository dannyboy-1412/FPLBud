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
    let intervalId = 0;
    const timeoutId = window.setTimeout(() => {
      tick();
      intervalId = window.setInterval(tick, 60_000);
    }, 60_000 - (Date.now() % 60_000));
    return () => {
      window.clearTimeout(timeoutId);
      window.clearInterval(intervalId);
    };
  }, [iso]);
  return (
    <span className={`masthead-clock nums${warn ? " is-warn" : ""}`}>
      <span className="masthead-clock-sep"> · </span>
      <span className="masthead-clock-prefix">Deadline in </span>
      {clock || "\u00a0"}
    </span>
  );
}
