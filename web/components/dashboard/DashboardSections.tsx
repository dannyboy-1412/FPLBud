"use client";

import { useLinkStatus } from "next/link";
import { useSelectedLayoutSegment } from "next/navigation";
import { IntentPrefetchLink } from "@/components/dashboard/IntentPrefetchLink";

export const DASHBOARD_SECTIONS = [
  { id: "plans", label: "Plans", href: "/dashboard" },
  { id: "squad", label: "My squad", href: "/dashboard/squad" },
  { id: "season", label: "My season", href: "/dashboard/season" },
  { id: "market", label: "Market", href: "/dashboard/market" },
  { id: "insights", label: "Insights", href: "/dashboard/insights" },
] as const;

function PendingDot() {
  const { pending } = useLinkStatus();
  return (
    <span
      aria-hidden
      className={`inline-block w-1.5 h-1.5 ml-1 rounded-full bg-vermilion align-middle ${pending ? "opacity-100" : "opacity-0"}`}
    />
  );
}

export function DashboardSections() {
  const segment = useSelectedLayoutSegment();
  const current = segment ?? "plans";
  return (
    <nav className="flex flex-wrap gap-7 border-b border-rule my-8" aria-label="Dashboard sections">
      {DASHBOARD_SECTIONS.map((section) => {
        const active = current === section.id;
        return (
          <IntentPrefetchLink
            key={section.id}
            href={section.href}
            prefetchOnIntent="shell"
            aria-current={active ? "page" : undefined}
            className={`no-underline pb-3 pt-2 font-[family-name:var(--font-fraunces)] text-2xl font-semibold ${
              active ? "text-ink shadow-[inset_0_3px_0_var(--vermilion)]" : "text-ink-faint"
            }`}
          >
            {section.label}
            <PendingDot />
          </IntentPrefetchLink>
        );
      })}
    </nav>
  );
}
