"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { useWakeRetry } from "@/components/programme/useWakeRetry";

export function ApiNotice({
  message,
  status,
  retry,
}: {
  message?: string;
  status?: number;
  retry?: () => void;
}) {
  const router = useRouter();
  const refresh = useCallback(() => router.refresh(), [router]);
  const waking = message == null;
  const wake = useWakeRetry(waking, retry ?? refresh);
  const detail = status === 401 ? "Sign in again to open this page." : message;

  return (
    <div role="status" aria-live="polite">
      <p className="kicker">{waking ? "Hold the edition" : "Correction"}</p>
      <h1 className="mt-2">{waking ? "The press room is waking up" : "Something went to press wrong"}</h1>
      <p className="caption mt-3">
        {waking
          ? wake.exhausted
            ? "The data service is still asleep. Try again in a moment."
            : "The data service sleeps when it is idle, then needs a few minutes to answer. This page checks again on its own."
          : detail}
      </p>
      {status === 401 ? (
        <Link href="/login" className="btn btn-primary mt-6">
          Sign in
        </Link>
      ) : (
        <button type="button" className="btn btn-secondary mt-6" onClick={wake.retryNow}>
          Try again
        </button>
      )}
    </div>
  );
}
