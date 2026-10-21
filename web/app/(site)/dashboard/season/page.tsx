import { Suspense } from "react";
import { SeasonSection } from "@/components/dashboard/stats/SeasonSection";
import { StatsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";

export default function SeasonPage() {
  return (
    <SectionError>
      <Suspense fallback={<StatsSkeleton />}>
        <SeasonSection />
      </Suspense>
    </SectionError>
  );
}
