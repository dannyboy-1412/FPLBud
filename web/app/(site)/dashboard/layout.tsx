import { Suspense, type ReactNode } from "react";
import { redirect } from "next/navigation";
import { DashboardSections } from "@/components/dashboard/DashboardSections";
import { HeadingSkeleton } from "@/components/programme/Skeletons";
import { accountNotice, loadAccount } from "@/lib/server/render-api";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<HeadingSkeleton />}>
      <DashboardFrame>{children}</DashboardFrame>
    </Suspense>
  );
}

async function DashboardFrame({ children }: { children: ReactNode }) {
  const account = await loadAccount();
  if (!account.ok) {
    return (
      <>
        {accountNotice(account)}
        {children}
      </>
    );
  }
  if (!account.me.profile.fpl_entry_id) redirect("/onboarding");
  const { me, meta } = account;
  return (
    <div className="matchday">
      <div className="mb-6">
        <p className="kicker">{meta?.next_event ? `Gameweek ${meta.next_event.id}` : "Dashboard"}</p>
        <h1 className="mt-1">{me.profile.fpl_team_name ?? "Your team"}</h1>
      </div>
      <DashboardSections />
      {children}
    </div>
  );
}
