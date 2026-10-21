import { Suspense, type ReactNode } from "react";
import { redirect } from "next/navigation";
import { DashboardSections } from "@/components/dashboard/DashboardSections";
import { EditionProvider } from "@/components/dashboard/EditionProvider";
import { PitchWithIncoming } from "@/components/dashboard/PitchWithIncoming";
import { RerunButton } from "@/components/dashboard/RerunButton";
import { BroadsheetSkeleton, HeadingSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { Pitch } from "@/components/programme/Pitch";
import { TeamSheet } from "@/components/programme/TeamSheet";
import { getLatestRun, getMe, getMyTeam, loadMeta } from "@/lib/server/data";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <EditionProvider>
      <div className="matchday">
        <Suspense fallback={<HeadingSkeleton />}>
          <DashboardHeader />
        </Suspense>
        <Suspense fallback={<BroadsheetSkeleton />}>
          <SectionError>
            <TeamSection />
          </SectionError>
        </Suspense>
        <DashboardSections />
        {children}
      </div>
    </EditionProvider>
  );
}

async function DashboardHeader() {
  const [me, meta, run] = await Promise.all([
    getMe(),
    loadMeta().catch(() => null),
    getLatestRun().catch(() => null),
  ]);
  if (!me.profile.fpl_entry_id) redirect("/onboarding");
  const running = Boolean(run && (run.status === "queued" || run.status === "running"));
  return (
    <div className="flex justify-between items-end gap-4 mb-6">
      <div>
        <p className="kicker">{meta?.next_event ? `Gameweek ${meta.next_event.id}` : "Dashboard"}</p>
        <h1 className="mt-1">{me.profile.fpl_team_name ?? "Your team"}</h1>
      </div>
      <RerunButton disabled={running} />
    </div>
  );
}

async function TeamSection() {
  const team = await getMyTeam();
  if (!team) return null;
  return (
    <div className="broadsheet">
      <Suspense fallback={<Pitch team={team} />}>
        <PitchWithIncoming team={team} runPromise={getLatestRun()} />
      </Suspense>
      <div className="col-rule" />
      <TeamSheet team={team} />
    </div>
  );
}
