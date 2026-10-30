"use client";

import { useLinkStatus } from "next/link";
import { useSelectedLayoutSegment } from "next/navigation";
import { IntentPrefetchLink } from "@/components/dashboard/IntentPrefetchLink";

export const DASHBOARD_SECTIONS = [
  { id: "team", label: "Team", href: "/dashboard", available: true },
  { id: "squad", label: "My squad", href: "/dashboard/squad", available: true },
  { id: "plans", label: "Plans", href: "/dashboard/plans", available: false },
  { id: "insights", label: "Insights", href: "/dashboard/insights", available: false },
] as const;

const tabClass = "pb-3 pt-2 font-[family-name:var(--font-fraunces)] text-2xl font-semibold";

function PendingDot() {
  const { pending } = useLinkStatus();
  return (
    <span
      aria-hidden
      className={`inline-block w-1.5 h-1.5 ml-1 rounded-full bg-vermilion align-middle ${pending ? "opacity-100" : "opacity-0"}`}
    />
  );
}

function SectionTab({
  section,
  active,
}: {
  section: (typeof DASHBOARD_SECTIONS)[number];
  active: boolean;
}) {
  if (!section.available) {
    return (
      <span
        role="link"
        aria-disabled="true"
        aria-describedby="dashboard-coming-soon"
        className={`${tabClass} cursor-not-allowed text-ink-faint opacity-45`}
      >
        {section.label}
      </span>
    );
  }

  return (
    <IntentPrefetchLink
      href={section.href}
      prefetchOnIntent="shell"
      aria-current={active ? "page" : undefined}
      className={`no-underline ${tabClass} ${
        active ? "text-ink shadow-[inset_0_3px_0_var(--vermilion)]" : "text-ink-faint"
      }`}
    >
      {section.label}
      <PendingDot />
    </IntentPrefetchLink>
  );
}

export function DashboardSections() {
  const segment = useSelectedLayoutSegment();
  const current = segment ?? "team";
  const firstUnavailable = DASHBOARD_SECTIONS.findIndex((section) => !section.available);

  return (
    <nav className="flex flex-wrap items-end gap-x-7 gap-y-3 border-b border-rule my-8" aria-label="Dashboard sections">
      {DASHBOARD_SECTIONS.map((section, index) => (
        <span key={section.id} className="contents">
          {index === firstUnavailable ? (
            <span id="dashboard-coming-soon" className="kicker pb-3.5 text-vermilion">
              Coming soon
            </span>
          ) : null}
          <SectionTab section={section} active={current === section.id} />
        </span>
      ))}
    </nav>
  );
}
