import { Suspense } from "react";
import { TeamView } from "@/components/programme/TeamReport";
import { TeamViewSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { getMyTeam, getPositionLeaders } from "@/lib/server/data";

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
  const [team, leaders] = await Promise.all([getMyTeam(), getPositionLeaders()]);
  if (!team) return null;
  return <TeamView team={team} leaders={leaders} showHeader={false} lineup="ready" />;
}
