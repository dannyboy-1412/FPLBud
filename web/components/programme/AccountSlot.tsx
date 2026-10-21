import Link from "next/link";
import { getSignedIn } from "@/lib/server/session";

export async function AccountSlot() {
  const signedIn = await getSignedIn();
  if (!signedIn) {
    return (
      <Link href="/login" className="btn-text">
        Sign in
      </Link>
    );
  }
  return (
    <Link
      href="/settings"
      className="w-7 h-7 rounded-full border border-ink grid place-items-center text-[11px] font-semibold bg-paper-deep"
      aria-label="Account"
    >
      {signedIn.initial}
    </Link>
  );
}
