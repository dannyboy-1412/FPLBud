"use client";

import { useState } from "react";
import { rememberPendingEntry } from "@/lib/server/actions";
import { createClient } from "@/lib/supabase/client";

export function GoogleButton({
  label = "Sign in with Google",
  entryId,
}: {
  label?: string;
  entryId?: number;
}) {
  const [pending, setPending] = useState(false);
  async function signIn() {
    setPending(true);
    if (entryId) {
      try {
        await rememberPendingEntry(entryId);
      } catch {
        /* still sign in */
      }
    }
    const supabase = createClient();
    const site = process.env.NEXT_PUBLIC_SITE_URL ?? window.location.origin;
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${site}/auth/callback` },
    });
  }
  return (
    <button type="button" className="btn btn-google w-full" onClick={signIn} disabled={pending}>
      <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
        <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 3l5.7-5.7C34.2 6.1 29.4 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z" />
        <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 12 24 12c3.1 0 5.8 1.1 8 3l5.7-5.7C34.2 6.1 29.4 4 24 4 16.3 4 9.6 8.3 6.3 14.7z" />
        <path fill="#4CAF50" d="M24 44c5.2 0 10-2 13.6-5.2l-6.3-5.2C29.2 35.3 26.7 36 24 36c-5.3 0-9.7-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
        <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-1.1 3.2-3.5 5.8-6.6 7.3l6.3 5.2C38.4 37.3 44 31.5 44 24c0-1.2-.1-2.3-.4-3.5z" />
      </svg>
      {pending ? "Opening Google..." : label}
    </button>
  );
}
