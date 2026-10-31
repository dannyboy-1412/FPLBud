import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";
export const maxDuration = 60;

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

type SendBody = {
  text?: string;
  thread_id?: string;
  client_msg_id?: string;
};

export async function POST(request: Request) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    return Response.json({ detail: "sign in required" }, { status: 401 });
  }
  const body = (await request.json()) as SendBody;
  const text = typeof body.text === "string" ? body.text : "";
  const threadId = await ensureThread(token, body.thread_id);
  if (threadId instanceof Response) return threadId;

  const upstream = await fetch(`${API_URL}/chat/threads/${threadId}/messages`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      "X-FPLBud-Client": "web",
    },
    body: JSON.stringify({ text, client_msg_id: body.client_msg_id ?? null }),
  });
  const headers = new Headers();
  headers.set("X-FPLBud-Thread", threadId);
  if (!upstream.ok || !upstream.body) {
    headers.set("Content-Type", upstream.headers.get("content-type") ?? "application/json");
    return new Response(upstream.body, { status: upstream.status, headers });
  }
  headers.set("Content-Type", "text/event-stream");
  headers.set("Cache-Control", "no-cache");
  return new Response(upstream.body, { status: 200, headers });
}

async function ensureThread(token: string, requested: string | undefined): Promise<string | Response> {
  if (requested) return requested;
  const created = await fetch(`${API_URL}/chat/threads`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: "{}",
  });
  if (!created.ok) {
    return new Response(created.body, {
      status: created.status,
      headers: { "Content-Type": created.headers.get("content-type") ?? "application/json" },
    });
  }
  const thread = (await created.json()) as { id?: string };
  if (!thread.id) {
    return Response.json({ detail: "Could not start a chat." }, { status: 502 });
  }
  return thread.id;
}
