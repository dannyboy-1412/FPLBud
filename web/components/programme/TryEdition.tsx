"use client";

import { useState } from "react";
import { PlanArticle } from "@/components/programme/PlanArticle";
import type { HorizonPlan, HorizonTab } from "@/lib/api";

const HORIZONS = ["1", "3", "5"] as const;

export function ReportPlans({ plans }: { plans: Record<string, HorizonPlan> }) {
  const available = HORIZONS.filter((h) => plans[h]);
  const [tab, setTab] = useState<HorizonTab>((available[0] ?? "1") as HorizonTab);
  const selected = available.includes(tab) ? tab : available[0];
  const plan = selected ? plans[selected] : undefined;
  if (!plan) return <p className="caption">Plans aren&apos;t ready yet.</p>;
  return (
    <>
      {available.length > 1 ? (
        <div className="flex gap-7 border-b border-rule mb-6" role="tablist">
          {available.map((h) => (
            <button
              key={h}
              type="button"
              role="tab"
              aria-selected={selected === h}
              className={`bg-transparent border-0 pb-3 pt-2 cursor-pointer font-[family-name:var(--font-fraunces)] text-2xl font-semibold ${
                selected === h ? "text-ink shadow-[inset_0_3px_0_var(--vermilion)]" : "text-ink-faint"
              }`}
              onClick={() => setTab(h)}
            >
              {h === "1" ? "Next GW" : `Next ${h}`}
            </button>
          ))}
        </div>
      ) : null}
      <PlanArticle plan={plan} />
    </>
  );
}
