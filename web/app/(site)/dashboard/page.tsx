import { Suspense } from "react";
import { TeamView } from "@/components/programme/TeamReport";
import { TeamPitchSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { loadAccount, renderApi } from "@/lib/server/render-api";
import { getMyTeam } from "@/lib/server/data";

// 30 minutes. Returning to Team reuses this render instead of fetching it again.
export const unstable_dynamicStaleTime = 1800;

export default function DashboardPage() {
  return (
    <SectionError>
      <Suspense fallback={<TeamPitchSkeleton />}>
        <SavedTeam />
      </Suspense>
    </SectionError>
  );
}

async function SavedTeam() {
  const account = await loadAccount();
  if (!account.ok) return null;
  return renderApi(async () => {
    const team = await getMyTeam();
    if (!team) return null;
    return <TeamView team={team} showHeader={false} lineup="ready" showStats={false} />;
  });
}
