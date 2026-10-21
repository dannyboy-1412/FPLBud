import { Suspense } from "react";
import { MarketSection } from "@/components/dashboard/stats/MarketSection";
import { StatsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";

export default function MarketPage() {
  return (
    <SectionError>
      <Suspense fallback={<StatsSkeleton />}>
        <MarketSection />
      </Suspense>
    </SectionError>
  );
}
