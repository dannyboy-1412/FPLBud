import { Suspense } from "react";
import { SquadSection } from "@/components/dashboard/stats/SquadSection";
import { StatsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";

export default function SquadPage() {
  return (
    <SectionError>
      <Suspense fallback={<StatsSkeleton />}>
        <SquadSection />
      </Suspense>
    </SectionError>
  );
}
