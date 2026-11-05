import Link from "next/link";
import { getSignedIn } from "@/lib/server/session";

export async function AccountSlot() {
  const signedIn = await getSignedIn();
  if (!signedIn) {
    return (
      <Link href="/login" className="masthead-signin">
        <span>Sign in</span>
      </Link>
    );
  }
  return (
    <Link href="/settings" className="masthead-account" aria-label="Account settings">
      <span className="masthead-avatar">{signedIn.initial}</span>
    </Link>
  );
}
