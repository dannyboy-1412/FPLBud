import { Suspense } from "react";
import { notFound, redirect } from "next/navigation";
import { LandingLookup } from "@/components/programme/LandingLookup";
import { TeamViewSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { TeamView } from "@/components/programme/TeamReport";
import { isTeamNotFound, type PublicTeam } from "@/lib/api";
import { getMe, getPositionLeaders, getPublicTeam } from "@/lib/server/data";
import { getAccessToken } from "@/lib/server/session";
import { parseTeamId } from "@/lib/team-id";

export default function TryPage({ params }: PageProps<"/try/[entryId]">) {
  return (
    <Suspense fallback={<TeamViewSkeleton />}>
      <SectionError>
        <TryContent params={params} />
      </SectionError>
    </Suspense>
  );
}

async function TryContent({ params }: { params: PageProps<"/try/[entryId]">["params"] }) {
  const { entryId } = await params;
  const parsed = parseTeamId(entryId);
  if (!parsed.ok) notFound();
  return <TryTeam entryId={parsed.id} />;
}

async function TryTeam({ entryId }: { entryId: number }) {
  const token = await getAccessToken();
  if (token) {
    const me = await getMe();
    if (me.profile.fpl_entry_id === entryId) redirect("/dashboard");
  }
  const leadersPromise = getPositionLeaders();
  let team: PublicTeam;
  try {
    team = await getPublicTeam(entryId);
  } catch (err) {
    if (isTeamNotFound(err)) return <UnknownTeam />;
    throw err;
  }
  return <TeamView team={team} leaders={await leadersPromise} lineup="locked" />;
}

function UnknownTeam() {
  return (
    <>
      <p className="kicker">Correction</p>
      <h1 className="mt-1">No team with that ID</h1>
      <p className="caption mt-2">Check the number in your Points page URL.</p>
      <div className="mt-8 max-w-xl">
        <LandingLookup />
      </div>
    </>
  );
}
