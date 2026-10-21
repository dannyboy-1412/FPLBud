import { Suspense } from "react";
import { AgentRunLive } from "@/components/dashboard/AgentRunLive";
import { DashboardTabs } from "@/components/dashboard/DashboardTabs";
import { PlanSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { getLatestRun } from "@/lib/server/data";

export default function PlansPage() {
  return (
    <>
      <DashboardTabs />
      <Suspense fallback={<PlanSkeleton />}>
        <SectionError>
          <EditionSection />
        </SectionError>
      </Suspense>
    </>
  );
}

async function EditionSection() {
  return <AgentRunLive initial={await getLatestRun()} />;
}
