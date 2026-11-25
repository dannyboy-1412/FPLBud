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
    <div className="team-record-page">
      <header className="team-record">
        <h1>{me.profile.fpl_team_name ?? "Your team"}</h1>
        {meta?.next_event ? <p className="team-record-when">Gameweek {meta.next_event.id}</p> : null}
      </header>
      <DashboardSections />
      {children}
    </div>
  );
}
