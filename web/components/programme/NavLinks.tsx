"use client";

import Link from "next/link";
import { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";

function PendingDot() {
  const { pending } = useLinkStatus();
  return (
    <span
      aria-hidden
      className={`inline-block w-1.5 h-1.5 ml-1 rounded-full bg-vermilion align-middle ${pending ? "opacity-100" : "opacity-0"}`}
    />
  );
}

function NavItem({ href, label, current }: { href: string; label: string; current: boolean }) {
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className="font-medium no-underline aria-[current=page]:underline underline-offset-[6px] decoration-2"
    >
      {label}
      <PendingDot />
    </Link>
  );
}

export function NavLinks() {
  const pathname = usePathname();
  return (
    <>
      <NavItem href="/dashboard" label="Dashboard" current={pathname.startsWith("/dashboard")} />
      <NavItem href="/players" label="Players" current={pathname.startsWith("/players")} />
      <NavItem href="/how-it-works" label="How it works" current={pathname.startsWith("/how-it-works")} />
    </>
  );
}
