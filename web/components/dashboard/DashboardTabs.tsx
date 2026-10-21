"use client";

import type { HorizonTab } from "@/lib/api";
import { useEdition } from "@/components/dashboard/EditionProvider";

export function DashboardTabs() {
  const { tab, setTab } = useEdition();
  return (
    <div className="flex gap-7 border-b border-rule my-8" role="tablist">
      {(["1", "3", "5"] as const).map((h) => (
        <button
          key={h}
          type="button"
          role="tab"
          aria-selected={tab === h}
          className={`bg-transparent border-0 pb-3 pt-2 cursor-pointer font-[family-name:var(--font-fraunces)] text-2xl font-semibold ${tab === h ? "text-ink shadow-[inset_0_3px_0_var(--vermilion)]" : "text-ink-faint"}`}
          onClick={() => setTab(h as HorizonTab)}
        >
          {h === "1" ? "Next GW" : `Next ${h}`}
        </button>
      ))}
    </div>
  );
}
