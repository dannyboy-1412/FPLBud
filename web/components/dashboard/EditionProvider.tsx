"use client";

import { createContext, use, useMemo, useState, type ReactNode } from "react";
import type { AgentRun, HorizonTab } from "@/lib/api";

type EditionContextValue = {
  tab: HorizonTab;
  setTab: (tab: HorizonTab) => void;
  optimisticRun: AgentRun | null;
  setOptimisticRun: (run: AgentRun | null) => void;
};

const EditionContext = createContext<EditionContextValue | null>(null);

export function EditionProvider({ children }: { children: ReactNode }) {
  const [tab, setTab] = useState<HorizonTab>("1");
  const [optimisticRun, setOptimisticRun] = useState<AgentRun | null>(null);
  const value = useMemo(
    () => ({ tab, setTab, optimisticRun, setOptimisticRun }),
    [tab, optimisticRun],
  );
  return <EditionContext value={value}>{children}</EditionContext>;
}

export function useEdition() {
  const ctx = use(EditionContext);
  if (!ctx) throw new Error("useEdition must be used within EditionProvider");
  return ctx;
}

export function queuedRun(id: number): AgentRun {
  return {
    id,
    status: "queued",
    stage: "context",
    progress: 0,
    error: null,
    created_at: new Date().toISOString(),
    finished_at: null,
    data_version: null,
    results: null,
  };
}
