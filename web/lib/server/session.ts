import "server-only";

import { connection } from "next/server";
import { cache } from "react";
import { createClient } from "@/lib/supabase/server";

export const getAccessToken = cache(async (): Promise<string | null> => {
  await connection();
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
});

export const getSignedIn = cache(async (): Promise<{ initial: string } | null> => {
  await connection();
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const session = data.session;
  if (!session) return null;
  const meta = session.user.user_metadata ?? {};
  const name = meta.full_name ?? meta.name ?? session.user.email ?? "•";
  return { initial: String(name).slice(0, 1).toUpperCase() };
});
