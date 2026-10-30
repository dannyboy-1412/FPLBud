import { Suspense } from "react";
import { InsightsSection } from "@/components/dashboard/stats/InsightsSection";
import { StatsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";

// 30 minutes. Returning to Insights reuses this render instead of fetching it again.
export const unstable_dynamicStaleTime = 1800;

export default function InsightsPage({ searchParams }: PageProps<"/dashboard/insights">) {
  return (
    <SectionError>
      <Suspense fallback={<StatsSkeleton />}>
        <InsightsSection searchParams={searchParams} />
      </Suspense>
    </SectionError>
  );
}
