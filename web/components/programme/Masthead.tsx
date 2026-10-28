import Link from "next/link";
import { Suspense } from "react";
import { AccountSlot } from "@/components/programme/AccountSlot";
import { GameweekLine } from "@/components/programme/GameweekLine";
import { NavLinks } from "@/components/programme/NavLinks";

export function Masthead() {
  return (
    <>
      <header className="masthead grid grid-cols-[1fr_auto_1fr] items-center h-[72px] gap-4">
        <Link href="/" className="wordmark">
          FPL<em>Bud</em>
          <span className="dot">.</span>
        </Link>
        <Suspense fallback={<span className="kicker text-center">The FPL tactics column</span>}>
          <GameweekLine />
        </Suspense>
        <nav className="flex gap-5 justify-end items-center">
          <Suspense
            fallback={
              <span className="font-medium">Dashboard</span>
            }
          >
            <NavLinks />
          </Suspense>
          <Suspense fallback={<span className="w-7 h-7" aria-hidden />}>
            <AccountSlot />
          </Suspense>
        </nav>
      </header>
      <div className="double-rule" />
    </>
  );
}
