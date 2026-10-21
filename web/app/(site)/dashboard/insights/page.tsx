import { Suspense } from "react";
import { InsightsSection } from "@/components/dashboard/stats/InsightsSection";
import { StatsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";

type InsightsSearch = Promise<{ pos?: string | string[] }>;

function parsePosition(value?: string | string[]): number | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  const n = Number(raw);
  return n >= 1 && n <= 4 ? n : undefined;
}

export default function InsightsPage({ searchParams }: { searchParams: InsightsSearch }) {
  return (
    <SectionError>
      <Suspense fallback={<StatsSkeleton />}>
        <InsightsBody searchParams={searchParams} />
      </Suspense>
    </SectionError>
  );
}

async function InsightsBody({ searchParams }: { searchParams: InsightsSearch }) {
  const sp = await searchParams;
  return <InsightsSection position={parsePosition(sp.pos)} />;
}
