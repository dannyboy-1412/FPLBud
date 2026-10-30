import { Suspense } from "react";
import { TeamView } from "@/components/programme/TeamReport";
import { TeamViewSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { loadAccount, renderApi } from "@/lib/server/render-api";
import { getMyTeam, getPositionLeaders } from "@/lib/server/data";

// 30 minutes. Returning to Team reuses this render instead of fetching it again.
export const unstable_dynamicStaleTime = 1800;

export default function DashboardPage() {
  return (
    <SectionError>
      <Suspense fallback={<TeamViewSkeleton />}>
        <SavedTeam />
      </Suspense>
    </SectionError>
  );
}

async function SavedTeam() {
  const account = await loadAccount();
  if (!account.ok) return null;
  return renderApi(async () => {
    const [team, leaders] = await Promise.all([getMyTeam(), getPositionLeaders()]);
    if (!team) return null;
    return <TeamView team={team} leaders={leaders} showHeader={false} lineup="ready" />;
  });
}
