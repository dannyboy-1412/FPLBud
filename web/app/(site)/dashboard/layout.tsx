import { Suspense, type ReactNode } from "react";
import { redirect } from "next/navigation";
import { DashboardSections } from "@/components/dashboard/DashboardSections";
import { HeadingSkeleton } from "@/components/programme/Skeletons";
import { getMe, loadMeta } from "@/lib/server/data";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="matchday">
      <Suspense fallback={<HeadingSkeleton />}>
        <DashboardHeader />
      </Suspense>
      <DashboardSections />
      {children}
    </div>
  );
}

async function DashboardHeader() {
  const [me, meta] = await Promise.all([getMe(), loadMeta().catch(() => null)]);
  if (!me.profile.fpl_entry_id) redirect("/onboarding");
  return (
    <div className="mb-6">
      <p className="kicker">{meta?.next_event ? `Gameweek ${meta.next_event.id}` : "Dashboard"}</p>
      <h1 className="mt-1">{me.profile.fpl_team_name ?? "Your team"}</h1>
    </div>
  );
}
