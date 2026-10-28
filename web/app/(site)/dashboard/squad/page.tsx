import { Suspense } from "react";
import { SquadSection } from "@/components/dashboard/stats/SquadSection";
import { StatsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";

// 30 minutes. Returning to My squad reuses this render instead of fetching it again.
export const unstable_dynamicStaleTime = 1800;

export default function SquadPage() {
  return (
    <SectionError>
      <Suspense fallback={<StatsSkeleton />}>
        <SquadSection />
      </Suspense>
    </SectionError>
  );
}
