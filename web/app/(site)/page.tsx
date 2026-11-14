import Link from "next/link";
import { Suspense } from "react";
import { GoogleButton } from "@/components/programme/GoogleButton";
import { LandingLookup } from "@/components/programme/LandingLookup";
import { LandingPitch } from "@/components/programme/LandingPitch";
import { type Profile } from "@/lib/api";
import { getMe, loadMeta } from "@/lib/server/data";
import { getSignedIn } from "@/lib/server/session";

const PLAIN_HEADLINE = "Your XI, captain and transfer, worked out";

const STEPS = [
  ["Import", "A public team ID. No FPL password. Free transfers and selling prices come from the public record."],
  ["Score", "Form, fixture difficulty, home games and expected goals and assists, ranked within position."],
  ["Solve", "FPLBud picks the XI, the bench, the captain and the transfers that project the most points."],
] as const;

export default function LandingPage() {
  return (
    <div className="landing">
      <div className="landing-hero">
        <div className="landing-copy">
          <h1>
            <Suspense fallback={PLAIN_HEADLINE}>
              <GameweekHeadline />
            </Suspense>
          </h1>
          <Suspense fallback={<LandingCopyFallback />}>
            <LandingCopy />
          </Suspense>
        </div>
        <LandingPitch />
      </div>
      <section className="landing-sequence">
        <h2>How a squad is chosen</h2>
        <ol className="landing-steps">
          {STEPS.map(([title, detail]) => (
            <li key={title} className="landing-step">
              <h3>{title}</h3>
              <p className="prose-body">{detail}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

async function GameweekHeadline() {
  const meta = await loadMeta().catch(() => null);
  const event = meta?.next_event ?? meta?.current_event;
  if (!event) return PLAIN_HEADLINE;
  return `Gameweek ${event.id}: your XI, captain and transfer`;
}

async function LandingCopy() {
  const signedIn = await getSignedIn();
  const profile = signedIn ? await memberProfile() : null;
  return (
    <>
      <p className="prose-body landing-lede">{lede(Boolean(signedIn), profile)}</p>
      {signedIn ? <MemberAction profile={profile} /> : <GuestAction />}
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

function lede(signedIn: boolean, profile: Profile | null) {
  if (!signedIn) {
    return "Bring a public team ID and get the starting XI, the captain and one transfer.";
  }
  if (profile && !profile.fpl_entry_id) {
    return "Finish setup to attach the one team on this account.";
  }
  const name = profile?.fpl_team_name;
  return name
    ? `${name} is saved here, with a plan for the XI, the captain and a transfer.`
    : "This account keeps one squad, with a plan for the XI, the captain and a transfer.";
}

function GuestAction() {
  return (
    <div className="landing-action">
      <LandingLookup />
      <div className="landing-signin">
        <p className="prose-body">Keep the three- and five-week plans on this account.</p>
        <GoogleButton />
      </div>
    </div>
  );
}

function MemberAction({ profile }: { profile: Profile | null }) {
  if (profile && !profile.fpl_entry_id) {
    return (
      <div className="landing-action">
        <Link href="/onboarding" className="btn btn-primary">
          Set your team
        </Link>
      </div>
    );
  }
  return (
    <div className="landing-action">
      <Link href="/dashboard" className="btn btn-primary">
        Open your plans
      </Link>
    </div>
  );
}

function LandingCopyFallback() {
  return (
    <div aria-hidden="true">
      <div className="skeleton landing-skeleton-lede" />
      <div className="skeleton landing-skeleton-field" />
    </div>
  );
}
