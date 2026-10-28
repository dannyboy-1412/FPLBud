import Link from "next/link";
import { Suspense } from "react";
import { GoogleButton } from "@/components/programme/GoogleButton";
import { LandingLookup } from "@/components/programme/LandingLookup";
import { type Profile } from "@/lib/api";
import { getMe } from "@/lib/server/data";
import { getSignedIn } from "@/lib/server/session";

const PLAN = [
  ["XI", "Eleven starters and a bench in order, inside the formation rules."],
  ["Captain", "The armband and the vice, on the players projected to return."],
  ["Transfer", "Who leaves, who arrives, or a roll. A hit only when the extra points clear it."],
] as const;

const STEPS = [
  ["1", "Import", "A public team ID. No FPL password. Free transfers and selling prices are estimated from the public record."],
  ["2", "Score", "Form, fixture difficulty, home games and expected goals and assists, ranked within position."],
  ["3", "Solve", "The optimiser picks the XI, the bench, the captain and the transfers that project the most points."],
] as const;

export default function LandingPage() {
  return (
    <Suspense fallback={<LandingSkeleton />}>
      <LandingBody />
    </Suspense>
  );
}

async function LandingBody() {
  const signedIn = await getSignedIn();
  const profile = signedIn ? await memberProfile() : null;
  const teamName = profile?.fpl_team_name;

  return (
    <>
      <p className="kicker">Squad recommendation</p>
      <h1 className="landing-title mt-3 max-w-[12ch]">
        Recommend the squad<span className="text-vermilion">.</span>
      </h1>
      <p className="prose-body text-xl mt-5 max-w-[46ch]">
        {signedIn
          ? teamName
            ? `${teamName} is the squad on this account. The plan names the starting XI, the bench, the captain and a transfer.`
            : "This account keeps one squad. The plan names the starting XI, the bench, the captain and a transfer."
          : "Bring a public team ID. FPLBud names the starting XI, the bench, the captain and a transfer, and only spends a hit when the extra points are worth it."}
      </p>

      <div className="double-rule mt-8" />
      <div className="broadsheet">
        {signedIn ? <MemberSquad profile={profile} /> : <GuestSquad />}
        <div className="col-rule" />
        <PlanAside signedIn={Boolean(signedIn)} />
      </div>

      <section className="mt-16">
        <p className="kicker">How a squad is chosen</p>
        <h2 className="mt-2">Import, score, solve</h2>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1px_1fr_1px_1fr] gap-6 mt-8">
          {STEPS.flatMap(([n, title, detail], index) => {
            const step = (
              <article key={n}>
                <p className="kicker">{title}</p>
                <span className="stat-xl block my-2">{n}</span>
                <p className="prose-body">{detail}</p>
              </article>
            );
            if (index === 0) return [step];
            return [<div key={`${n}-rule`} className="col-rule" aria-hidden="true" />, step];
          })}
        </div>
      </section>
    </>
  );
}

async function memberProfile(): Promise<Profile | null> {
  try {
    return (await getMe()).profile;
  } catch {
    return null;
  }
}

function GuestSquad() {
  return (
    <div>
      <p className="kicker">Your squad</p>
      <h2 className="mt-2">Start from a team ID</h2>
      <div className="mt-6">
        <LandingLookup />
      </div>
    </div>
  );
}

function MemberSquad({ profile }: { profile: Profile | null }) {
  if (profile && !profile.fpl_entry_id) {
    return (
      <div>
        <p className="kicker">Your squad</p>
        <h2 className="mt-2">One team on this account</h2>
        <p className="prose-body mt-3 max-w-[36ch]">
          The team ID is saved once. Finish setup to attach it.
        </p>
        <Link href="/onboarding" className="btn btn-primary mt-5">
          Set your team
        </Link>
      </div>
    );
  }

  return (
    <div>
      <p className="kicker">Your squad</p>
      <h2 className="mt-2">{profile?.fpl_team_name ?? "Your team"}</h2>
      <p className="prose-body mt-3 max-w-[36ch]">
        One account, one team. The recommendation uses the squad already saved here.
      </p>
      <Link href="/dashboard" className="btn btn-primary mt-5">
        Open your plans
      </Link>
    </div>
  );
}

function PlanAside({ signedIn }: { signedIn: boolean }) {
  const horizon = signedIn
    ? "Next week, the next three and the next five, on your dashboard, with chip notes."
    : "Next week from this lookup. Save the squad for the same plan over three and five weeks, with chip notes.";

  return (
    <aside className="border-t-[3px] border-vermilion pt-4">
      <p className="kicker">The recommendation</p>
      <h2 className="mt-2">What the plan decides</h2>
      <dl className="mt-4">
        {PLAN.map(([term, detail]) => (
          <div key={term} className="grid grid-cols-[6.5rem_1fr] gap-3 py-3 border-b border-rule">
            <dt className="kicker pt-1">{term}</dt>
            <dd className="prose-body m-0">{detail}</dd>
          </div>
        ))}
        <div className="grid grid-cols-[6.5rem_1fr] gap-3 py-3 border-b border-rule">
          <dt className="kicker pt-1">Horizon</dt>
          <dd className="prose-body m-0">{horizon}</dd>
        </div>
      </dl>
      {signedIn ? null : <GuestAction />}
    </aside>
  );
}

function GuestAction() {
  return (
    <div className="mt-5 max-w-xs">
      <p className="prose-body mb-3">Save the squad to keep the three- and five-week plans.</p>
      <GoogleButton />
    </div>
  );
}

function LandingSkeleton() {
  return (
    <div aria-hidden>
      <div className="skeleton h-3 w-40 mb-4" />
      <div className="skeleton h-16 w-72 max-w-full mb-3" />
      <div className="skeleton h-16 w-56 max-w-full mb-6" />
      <div className="skeleton h-6 w-full max-w-xl mb-8" />
      <div className="double-rule" />
      <div className="broadsheet">
        <div>
          <div className="skeleton h-3 w-24 mb-3" />
          <div className="skeleton h-8 w-48 mb-4" />
          <div className="skeleton h-16 w-full" />
        </div>
        <div className="col-rule" />
        <aside className="border-t-[3px] border-vermilion pt-4">
          <div className="skeleton h-3 w-36 mb-3" />
          <div className="skeleton h-8 w-56 mb-6" />
          <div className="skeleton h-16 w-full mb-3" />
          <div className="skeleton h-16 w-full mb-3" />
          <div className="skeleton h-16 w-full" />
        </aside>
      </div>
    </div>
  );
}
