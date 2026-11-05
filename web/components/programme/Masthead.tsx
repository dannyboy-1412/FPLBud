import Link from "next/link";
import { Suspense } from "react";
import { AccountSlot } from "@/components/programme/AccountSlot";
import { GameweekLine } from "@/components/programme/GameweekLine";
import { NavLinks } from "@/components/programme/NavLinks";

function DeadlineFallback() {
  return (
    <div className="masthead-deadline-fallback" aria-hidden="true">
      <span className="masthead-skeleton masthead-skeleton-long" />
      <span className="masthead-skeleton masthead-skeleton-short" />
    </div>
  );
}

function NavFallback() {
  return (
    <>
      <span className="masthead-link" aria-hidden="true">Dashboard</span>
      <span className="masthead-link" aria-hidden="true">Assistant</span>
    </>
  );
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
        <Link href="/" className="wordmark" aria-label="FPLBud home">
          FPL<em>Bud</em>
          <span className="dot" aria-hidden="true">.</span>
        </Link>
        <div className="masthead-edition">
          <Suspense fallback={<DeadlineFallback />}>
            <GameweekLine />
          </Suspense>
        </div>
        <nav className="masthead-nav" aria-label="Main">
          <Suspense fallback={<NavFallback />}>
            <NavLinks />
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
