import { Suspense } from "react";
import { ChatWorkspace } from "@/components/chat/ChatWorkspace";
import { getChatThread, getChatThreads, getChatUsage, loadMeta } from "@/lib/server/data";

export default function ChatPage({ searchParams }: PageProps<"/chat">) {
  return (
    <Suspense fallback={<ChatFallback />}>
      <ChatLoader searchParams={searchParams} />
    </Suspense>
  );
}

async function ChatLoader({ searchParams }: { searchParams: PageProps<"/chat">["searchParams"] }) {
  const params = await searchParams;
  const requested = firstParam(params.t);
  const [threadsResult, usage, threadResult, meta] = await Promise.all([
    getChatThreads(),
    getChatUsage(),
    requested ? getChatThread(requested) : Promise.resolve(null),
    loadMeta().catch(() => null),
  ]);

  if (threadsResult.status === "disabled" || threadResult?.status === "disabled") {
    return (
      <DeskNotice kicker="Assistant" title="The desk is closed" body="Chat is turned off for this account." />
    );
  }
  if (threadsResult.status === "error") {
    return <DeskNotice kicker="Assistant" title="The notebook didn't load" body={threadsResult.message} />;
  }
  if (threadResult?.status === "error") {
    return <DeskNotice kicker="Assistant" title="That conversation didn't load" body={threadResult.message} />;
  }

  const event = meta?.next_event ?? meta?.current_event ?? null;
  const active = threadResult?.status === "ok" ? threadResult : null;

  return (
    <ChatWorkspace
      key={active?.thread.id ?? (threadResult?.status === "missing" ? "missing" : "draft")}
      threads={threadsResult.threads}
      thread={active?.thread ?? null}
      messages={active?.messages ?? []}
      usage={usage}
      event={event}
      missing={threadResult?.status === "missing"}
    />
  );
}

function firstParam(value: string | string[] | undefined): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (Array.isArray(value)) return value.find((item) => item.trim()) ?? null;
  return null;
}

function DeskNotice({ kicker, title, body }: { kicker: string; title: string; body: string }) {
  return (
    <section className="chat-closed">
      <p className="kicker">{kicker}</p>
      <h1>{title}</h1>
      <p className="chat-closed-copy">{body}</p>
    </section>
  );
}

function ChatFallback() {
  return (
    <div className="chat-workspace" aria-hidden>
      <div className="chat-rail">
        <div className="skeleton h-11" />
        <div className="skeleton mt-4 h-7" />
        <div className="skeleton mt-2 h-7" />
      </div>
      <div className="chat-stage">
        <div className="skeleton mt-5 h-7 w-2/5 max-w-xs" />
      </div>
    </div>
  );
}
