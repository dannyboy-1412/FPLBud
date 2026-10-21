import { Suspense } from "react";
import { notFound } from "next/navigation";
import { LandingLookup } from "@/components/programme/LandingLookup";
import { StatsSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { GuestReport, MemberSections, ReportHeader, SquadScore } from "@/components/programme/TeamReport";
import { isTeamNotFound, type PublicTeam } from "@/lib/api";
import { getPublicTeam, getTeamReport } from "@/lib/server/data";
import { getAccessToken } from "@/lib/server/session";
import { parseTeamId } from "@/lib/team-id";

export default function TryPage({ params }: PageProps<"/try/[entryId]">) {
  return (
    <Suspense
      fallback={
        <>
          <div className="skeleton h-3 w-32 mb-2" />
          <div className="skeleton h-10 w-64 mb-6" />
          <div className="skeleton h-16 w-40 mb-8" />
          <StatsSkeleton />
        </>
      }
    >
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
  let team: PublicTeam;
  try {
    team = await getPublicTeam(entryId);
  } catch (err) {
    if (isTeamNotFound(err)) return <UnknownTeam />;
    throw err;
  }
  const token = await getAccessToken();
  if (!token) return <GuestReport team={team} />;
  return (
    <>
      <ReportHeader name={team.name} manager={team.manager} overallRank={team.overall_rank} />
      <SquadScore value={team.squad_score} caption="Starting XI, next gameweek." />
      <Suspense fallback={<StatsSkeleton />}>
        <SectionError>
          <SignedInReport entryId={entryId} />
        </SectionError>
      </Suspense>
    </>
  );
}

async function SignedInReport({ entryId }: { entryId: number }) {
  const report = await getTeamReport(entryId);
  return <MemberSections report={report} />;
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
