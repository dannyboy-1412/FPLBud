"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";

function PendingDot() {
  const { pending } = useLinkStatus();
  return <span aria-hidden className="masthead-pending" data-pending={pending ? "true" : undefined} />;
}

function NavItem({ href, label, current }: { href: string; label: string; current: boolean }) {
  return (
    <Link href={href} aria-current={current ? "page" : undefined} className="masthead-link">
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
      <NavItem href="/chat" label="Assistant" current={pathname.startsWith("/chat")} />
    </>
  );
}
