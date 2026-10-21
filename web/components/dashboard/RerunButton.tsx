"use client";

import { useState, useTransition } from "react";
import { queuedRun, useEdition } from "@/components/dashboard/EditionProvider";
import { rerunAgent } from "@/lib/server/actions";

export function RerunButton({ disabled }: { disabled?: boolean }) {
  const { optimisticRun, setOptimisticRun } = useEdition();
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const running =
    optimisticRun && (optimisticRun.status === "queued" || optimisticRun.status === "running");
  const busy = disabled || pending || Boolean(running);

  return (
    <div className="text-right">
      <button
        type="button"
        className="btn btn-secondary"
        disabled={busy}
        onClick={() => {
          setError(null);
          setOptimisticRun(queuedRun(0));
          startTransition(async () => {
            const result = await rerunAgent();
            if ("error" in result) {
              setOptimisticRun(null);
              setError(result.error);
              return;
            }
            setOptimisticRun(queuedRun(result.runId));
          });
        }}
      >
        {busy ? "Running…" : "Re-run agent"}
      </button>
      {error ? <p className="caption text-claret mt-2">{error}</p> : null}
    </div>
  );
}
