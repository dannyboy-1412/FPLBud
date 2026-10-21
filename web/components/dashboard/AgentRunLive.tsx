"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { GoingToPress } from "@/components/programme/GoingToPress";
import { PlanArticle } from "@/components/programme/PlanArticle";
import { queuedRun, useEdition } from "@/components/dashboard/EditionProvider";
import { api, type AgentRun } from "@/lib/api";
import { rerunAgent } from "@/lib/server/actions";
import { createClient } from "@/lib/supabase/client";

async function token() {
  const { data } = await createClient().auth.getSession();
  return data.session?.access_token ?? null;
}

export function AgentRunLive({ initial }: { initial: AgentRun | null }) {
  const { tab, optimisticRun, setOptimisticRun } = useEdition();
  const run = optimisticRun ?? initial;
  const [stalled, setStalled] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!run || (run.status !== "queued" && run.status !== "running") || run.id === 0) return;
    let delay = 2000;
    let elapsed = 0;
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await api<AgentRun>(`/agent/runs/${run.id}`, { token: await token() });
        if (cancelled) return;
        setOptimisticRun(next);
        elapsed += delay;
        if (elapsed > 60_000) setStalled(true);
        if (next.status === "succeeded" || next.status === "failed") {
          router.refresh();
          setOptimisticRun(null);
          return;
        }
        delay = Math.min(5000, delay + 500);
        timer = setTimeout(poll, delay);
      } catch {
        if (cancelled) return;
        timer = setTimeout(poll, delay);
      }
    };
    timer = setTimeout(poll, delay);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- restart only when the run id/status change
  }, [run?.id, run?.status, router, setOptimisticRun]);

  if (!run) {
    return <p className="caption">No edition yet.</p>;
  }

  const running = run.status === "queued" || run.status === "running";
  if (running || run.status === "failed") {
    return (
      <GoingToPress
        stage={run.stage}
        progress={run.progress ?? 0}
        error={run.error}
        stalled={stalled}
        onRetry={() => {
          setOptimisticRun(queuedRun(run.id));
          void rerunAgent().then((result) => {
            if ("ok" in result) setOptimisticRun(queuedRun(result.runId));
            router.refresh();
          });
        }}
      />
    );
  }

  const plan = run.results?.[tab];
  if (!plan) return <p className="caption">No edition yet.</p>;
  return <PlanArticle plan={plan} />;
}
