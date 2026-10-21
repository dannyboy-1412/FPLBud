import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { api } from "@/lib/api";
import { PENDING_ENTRY_COOKIE } from "@/lib/pending-entry";
import { createClient } from "@/lib/supabase/server";
import { parseTeamId } from "@/lib/team-id";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const site = process.env.NEXT_PUBLIC_SITE_URL ?? url.origin;
  if (!code) {
    return NextResponse.redirect(`${site}/login`);
  }
  const supabase = await createClient();
  await supabase.auth.exchangeCodeForSession(code);
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const store = await cookies();
  const pendingParsed = parseTeamId(store.get(PENDING_ENTRY_COOKIE)?.value ?? "");
  const pendingId = pendingParsed.ok ? pendingParsed.id : null;

  let dest = "/onboarding";
  if (session?.access_token) {
    try {
      const me = await api<{ profile: { fpl_entry_id: number | null } }>("/me", {
        token: session.access_token,
      });
      const saved = me.profile.fpl_entry_id;
      if (saved) {
        dest = pendingId ? `/try/${saved}` : "/dashboard";
      } else if (pendingId) {
        try {
          await api("/me/team", {
            method: "PUT",
            token: session.access_token,
            body: JSON.stringify({ entry_id: pendingId }),
          });
          dest = `/try/${pendingId}`;
        } catch {
          dest = "/onboarding";
        }
      }
    } catch {
      dest = "/onboarding";
    }
  }

  const response = NextResponse.redirect(`${site}${dest}`);
  response.cookies.delete(PENDING_ENTRY_COOKIE);
  return response;
}
