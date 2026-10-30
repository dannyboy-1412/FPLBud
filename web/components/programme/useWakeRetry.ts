"use client";

import { useEffect, useRef, useState } from "react";

const STALE_MS = 60_000;
const RETRY_MS = 10_000;

const bucket = {
  countKey: "fplbud-wake-count",
  atKey: "fplbud-wake-at",
};

function readAttempts() {
  try {
    const at = Number(sessionStorage.getItem(bucket.atKey) ?? "0");
    if (!at || Date.now() - at > STALE_MS) return 0;
    return Number(sessionStorage.getItem(bucket.countKey) ?? "0");
  } catch {
    return 0;
  }
}

function writeAttempts(count: number) {
  try {
    sessionStorage.setItem(bucket.countKey, String(count));
    sessionStorage.setItem(bucket.atKey, String(Date.now()));
  } catch {
    /* private mode */
  }
}

function clearAttempts() {
  try {
    sessionStorage.removeItem(bucket.countKey);
    sessionStorage.removeItem(bucket.atKey);
  } catch {
    /* private mode */
  }
}

export function useWakeRetry(enabled: boolean, retry: () => void, limit = 24) {
  const retryRef = useRef(retry);
  const [exhausted, setExhausted] = useState(false);

  useEffect(() => {
    retryRef.current = retry;
  }, [retry]);

  useEffect(() => {
    if (!enabled) return;
    if (readAttempts() >= limit) {
      setExhausted(true);
      return;
    }
    let cancelled = false;
    const loop = async () => {
      while (!cancelled && readAttempts() < limit) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
        if (cancelled) return;
        if (readAttempts() >= limit) break;
        const next = readAttempts() + 1;
        writeAttempts(next);
        retryRef.current();
      }
      if (!cancelled && readAttempts() >= limit) setExhausted(true);
    };
    void loop();
    return () => {
      cancelled = true;
    };
  }, [enabled, limit]);

  return {
    exhausted,
    retryNow() {
      clearAttempts();
      setExhausted(false);
      retryRef.current();
    },
  };
}
