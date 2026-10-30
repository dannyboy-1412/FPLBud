import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { api } from "@/lib/api";
import { PENDING_ENTRY_COOKIE } from "@/lib/pending-entry";
import { parseTeamId } from "@/lib/team-id";

type SessionCookie = {
  name: string;
  value: string;
  options?: Parameters<NextResponse["cookies"]["set"]>[2];
};

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const site = url.origin;
  if (!code) {
    return NextResponse.redirect(`${site}/login`);
  }

  const store = await cookies();
  const sessionCookies: SessionCookie[] = [];
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return store.getAll();
        },
        setAll(cookiesToSet) {
          sessionCookies.splice(0, sessionCookies.length, ...cookiesToSet);
          cookiesToSet.forEach(({ name, value, options }) => {
            store.set(name, value, options);
          });
        },
      },
    },
  );
  const { data, error } = await supabase.auth.exchangeCodeForSession(code);
  const session = error ? null : data.session;

  const pendingParsed = parseTeamId(store.get(PENDING_ENTRY_COOKIE)?.value ?? "");
  const pendingId = pendingParsed.ok ? pendingParsed.id : null;

  let dest = "/onboarding";
  if (!session?.access_token) {
    dest = "/login";
  } else {
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
  for (const cookie of sessionCookies) {
    response.cookies.set(cookie.name, cookie.value, cookie.options);
  }
  response.cookies.delete(PENDING_ENTRY_COOKIE);
  return response;
}
