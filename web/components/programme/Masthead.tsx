import Link from "next/link";
import { Suspense } from "react";
import { AccountSlot } from "@/components/programme/AccountSlot";
import { GameweekLine } from "@/components/programme/GameweekLine";
import { NavLinks } from "@/components/programme/NavLinks";
import { getSignedIn } from "@/lib/server/session";

function DeadlineFallback() {
  return (
    <div className="masthead-deadline-fallback" aria-hidden="true">
      <span className="masthead-skeleton masthead-skeleton-long" />
      <span className="masthead-skeleton masthead-skeleton-short" />
    </div>
  );
}

function Wordmark({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="wordmark" aria-label={label}>
      FPL<em>Bud</em>
      <span className="dot" aria-hidden="true">.</span>
    </Link>
  );
}

async function HomeMark() {
  const signedIn = await getSignedIn();
  if (!signedIn) return <Wordmark href="/" label="FPLBud home" />;
  return <Wordmark href="/chat" label="FPLBud assistant" />;
}

async function MemberNav() {
  const signedIn = await getSignedIn();
  if (!signedIn) return null;
  return <NavLinks />;
}

function AccountFallback() {
  return (
    <span className="masthead-account" aria-hidden="true">
      <span className="masthead-avatar" />
    </span>
  );
}

export function Masthead() {
  return (
    <>
      <header className="masthead">
        <Suspense fallback={<Wordmark href="/" label="FPLBud home" />}>
          <HomeMark />
        </Suspense>
        <div className="masthead-edition">
          <Suspense fallback={<DeadlineFallback />}>
            <GameweekLine />
          </Suspense>
        </div>
        <nav className="masthead-nav" aria-label="Main">
          <Suspense fallback={null}>
            <MemberNav />
          </Suspense>
          <Suspense fallback={<AccountFallback />}>
            <AccountSlot />
          </Suspense>
        </nav>
      </header>
      <div className="double-rule" />
    </>
  );
}
