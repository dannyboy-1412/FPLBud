"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Composer } from "@/components/chat/Composer";
import { Conversation } from "@/components/chat/Conversation";
import { PromptChips } from "@/components/chat/EmptyBriefing";
import { ThreadRail } from "@/components/chat/ThreadRail";
import type { BriefingSquad } from "@/components/chat/briefing";
import {
  emptyTurn,
  plainChatText,
  pushSse,
  reduceTurn,
  bubbleFromStored,
  type ChatBubble,
  type ChatUsage,
  type LiveTurn,
  type StoredMessage,
  type StoredThread,
} from "@/lib/chat";

const RAIL_KEY = "fplbud.chat.rail";

type BriefingEvent = { id: number; name: string; deadline_time: string };

export function ChatWorkspace({
  threads,
  thread,
  messages,
  usage,
  event,
  missing,
  teamPromise,
}: {
  threads: StoredThread[];
  thread: StoredThread | null;
  messages: StoredMessage[];
  usage: ChatUsage | null;
  event: BriefingEvent | null;
  missing: boolean;
  teamPromise: Promise<BriefingSquad | null>;
}) {
  const router = useRouter();
  const [notebook, setNotebook] = useState(threads);
  const [threadId, setThreadId] = useState<string | null>(thread?.id ?? null);
  const [bubbles, setBubbles] = useState<ChatBubble[]>(() => messages.map(bubbleFromStored));
  const [live, setLive] = useState<LiveTurn>(emptyTurn);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [narrow, setNarrow] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [fresh, setFresh] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const genRef = useRef(0);
  const liveRef = useRef(live);
  const busyRef = useRef(false);
  const drawerRef = useRef(false);
  const stopRef = useRef<() => void>(() => {});
  const startRef = useRef<() => void>(() => {});
  const closeRef = useRef<() => void>(() => {});
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const usageRef = useRef(usage);

  useLayoutEffect(() => {
    const page = document.querySelector(".page");
    page?.classList.add("page--app");
    return () => page?.classList.remove("page--app");
  }, []);

  useLayoutEffect(() => {
    setCollapsed(window.localStorage.getItem(RAIL_KEY) === "collapsed");
  }, []);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 1023px)");
    const sync = () => setNarrow(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (busyRef.current) {
          event.preventDefault();
          stopRef.current();
          return;
        }
        if (drawerRef.current) closeRef.current();
        return;
      }
      const command = event.metaKey || event.ctrlKey;
      if (command && event.shiftKey && event.key.toLowerCase() === "o") {
        event.preventDefault();
        startRef.current();
        return;
      }
      if (event.key !== "/" || command || event.altKey) return;
      const target = event.target;
      if (target instanceof HTMLElement && target.closest("input, textarea, select, [contenteditable='true']")) return;
      event.preventDefault();
      composerRef.current?.focus();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  function stop() {
    if (!busyRef.current) return;
    genRef.current += 1;
    const current = liveRef.current;
    abortRef.current?.abort();
    if (current.draft) {
      setBubbles((existing) => [...existing, answerFromTurn(current, true)]);
    }
    const cleared = { ...emptyTurn(), turnsLeft: current.turnsLeft, done: true };
    liveRef.current = cleared;
    setLive(cleared);
    busyRef.current = false;
    setBusy(false);
  }

  function startFresh() {
    if (busyRef.current) stop();
    setFresh(true);
    setDrawer(false);
    setThreadId(null);
    setBubbles([]);
    setDraft("");
    setAnnouncement("");
    const cleared = emptyTurn();
    liveRef.current = cleared;
    setLive(cleared);
    const url = new URL(window.location.href);
    if (url.searchParams.has("t")) {
      url.searchParams.delete("t");
      window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
    }
    router.push("/chat");
    composerRef.current?.focus();
  }

  useEffect(() => {
    usageRef.current = usage;
    drawerRef.current = drawer;
    stopRef.current = stop;
    startRef.current = startFresh;
    closeRef.current = closeDrawer;
  });

  async function ask(text: string) {
    const question = text.trim();
    if (!question || busyRef.current) return;
    const gen = genRef.current + 1;
    genRef.current = gen;
    const startedWithoutThread = threadId == null;
    busyRef.current = true;
    setBusy(true);
    setDraft("");
    setAnnouncement("");
    setBubbles((existing) => [...existing, userBubble(question)]);
    const cleared = emptyTurn();
    liveRef.current = cleared;
    setLive(cleared);
    const controller = new AbortController();
    abortRef.current = controller;
    const current = () => genRef.current === gen && !controller.signal.aborted;
    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: question,
          thread_id: threadId,
          client_msg_id: crypto.randomUUID(),
        }),
        signal: controller.signal,
      });
      if (!current()) return;
      const nextThread = response.headers.get("X-FPLBud-Thread");
      if (nextThread) touchThread(nextThread, question, startedWithoutThread);
      if (response.status === 429) {
        await response.body?.cancel();
        if (!current()) return;
        const limited = { ...emptyTurn(), error: limitMessage(usageRef.current), done: true };
        liveRef.current = limited;
        setLive(limited);
        return;
      }
      if (!response.ok || !response.body) {
        const detail = await readError(response);
        if (!current()) return;
        const failed = { ...emptyTurn(), error: detail, done: true };
        liveRef.current = failed;
        setLive(failed);
        return;
      }
      const finished = await readStream(response.body, (turn) => {
        if (!current()) return;
        liveRef.current = turn;
        setLive(turn);
      });
      if (!current()) return;
      if (finished.finalText) {
        setBubbles((existing) => [...existing, answerFromTurn(finished, false)]);
        setAnnouncement(plainChatText(finished.finalText));
        const resting = { ...emptyTurn(), turnsLeft: finished.turnsLeft, proposal: finished.proposal };
        liveRef.current = resting;
        setLive(resting);
      } else if (finished.draft && !finished.error) {
        const incomplete = { ...finished, error: "The answer stopped before it finished.", done: true };
        liveRef.current = incomplete;
        setLive(incomplete);
      } else {
        liveRef.current = finished;
        setLive(finished);
      }
    } catch (err) {
      if (!current() || isAbort(err)) return;
      const failed = { ...liveRef.current, error: "Chat is unavailable right now.", done: true };
      liveRef.current = failed;
      setLive(failed);
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      if (genRef.current === gen) {
        busyRef.current = false;
        setBusy(false);
      }
    }
  }

  function touchThread(id: string, question: string, startedWithoutThread: boolean) {
    setThreadId(id);
    if (startedWithoutThread) rememberThread(id);
    setNotebook((current) => {
      const existing = current.find((item) => item.id === id);
      const next: StoredThread = {
        id,
        title: existing?.title ?? question.slice(0, 60),
        message_count: (existing?.message_count ?? 0) + 1,
        updated_at: new Date().toISOString(),
      };
      return [next, ...current.filter((item) => item.id !== id)];
    });
  }

  function retry() {
    const last = [...bubbles].reverse().find((message) => message.role === "user");
    if (last) void ask(last.text);
  }

  function closeDrawer() {
    setDrawer(false);
    document.getElementById("chat-open-notebook")?.focus();
  }

  function toggleRail() {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(RAIL_KEY, next ? "collapsed" : "open");
      return next;
    });
  }

  function onDeleted(id: string) {
    setNotebook((current) => current.filter((item) => item.id !== id));
    if (id === threadId) startFresh();
    else setDrawer(false);
  }

  const asked = bubbles.find((message) => message.role === "user")?.text.trim().slice(0, 60);
  const title = notebook.find((item) => item.id === threadId)?.title?.trim() || asked || "New chat";
  const turnsLeft = live.turnsLeft ?? usage?.turns_left ?? null;
  const showLive = busy || Boolean(live.draft) || Boolean(live.error);
  const empty = bubbles.length === 0 && !showLive;
  const showRail = notebook.length > 0;
  const railCollapsed = showRail && collapsed && !narrow;
  const workspaceClass = ["chat-workspace", showRail ? "has-rail" : "", railCollapsed ? "is-collapsed" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={workspaceClass}>
      {narrow && drawer ? (
        <button type="button" className="chat-backdrop" aria-label="Close chats" onClick={() => setDrawer(false)} />
      ) : null}
      {showRail ? (
        <div
          className="chat-rail-slot"
          inert={narrow && !drawer ? true : undefined}
          aria-hidden={narrow && !drawer ? true : undefined}
        >
          <ThreadRail
            threads={notebook}
            activeId={threadId}
            open={drawer}
            drawer={narrow}
            collapsed={railCollapsed}
            canStart={threadId != null || bubbles.length > 0}
            onClose={closeDrawer}
            onToggle={toggleRail}
            onNew={startFresh}
            onDeleted={onDeleted}
          />
        </div>
      ) : null}
      <div className={empty ? "chat-stage is-empty" : "chat-stage"} inert={narrow && drawer ? true : undefined}>
        <Conversation
          title={title}
          bubbles={bubbles}
          live={live}
          busy={busy}
          event={event}
          missing={missing && !fresh}
          teamPromise={teamPromise}
          onRetry={retry}
          onOpenNotebook={narrow && showRail ? () => setDrawer(true) : null}
          onExpand={railCollapsed ? toggleRail : null}
        />
        <Composer
          inputRef={composerRef}
          value={draft}
          busy={busy}
          turnsLeft={turnsLeft}
          event={event}
          teamPromise={teamPromise}
          onChange={setDraft}
          onSend={() => void ask(draft)}
          onStop={stop}
        />
        {empty ? <PromptChips teamPromise={teamPromise} onAsk={(question) => void ask(question)} /> : null}
      </div>
      <div className="sr-only" aria-live="polite">
        {announcement}
      </div>
    </div>
  );
}

function userBubble(text: string): ChatBubble {
  return {
    role: "user",
    text,
    citations: [],
    toolsUsed: [],
    dataAsOf: null,
    messageId: null,
    disclaimers: [],
    createdAt: new Date().toISOString(),
    feedback: null,
    stopped: false,
    steps: [],
  };
}

function answerFromTurn(turn: LiveTurn, stopped: boolean): ChatBubble {
  return {
    role: "assistant",
    text: stopped ? turn.draft : (turn.finalText ?? ""),
    citations: stopped ? [] : turn.citations,
    toolsUsed: stopped ? [] : turn.toolsUsed,
    dataAsOf: stopped ? null : turn.dataAsOf,
    messageId: stopped ? null : turn.messageId,
    disclaimers: stopped ? [] : turn.disclaimers,
    createdAt: new Date().toISOString(),
    feedback: null,
    stopped,
    steps: stopped ? turn.steps.map((step) => ({ ...step, done: true })) : [],
  };
}

function rememberThread(id: string) {
  const url = new URL(window.location.href);
  if (url.searchParams.get("t") === id) return;
  url.searchParams.set("t", id);
  window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
}

function limitMessage(usage: ChatUsage | null): string {
  return `Daily limit reached. Resets at ${usage?.resets_at ?? "00:00 UTC"}.`;
}

function isAbort(err: unknown): boolean {
  return err instanceof Error && err.name === "AbortError";
}

async function readStream(body: ReadableStream<Uint8Array>, onTurn: (turn: LiveTurn) => void): Promise<LiveTurn> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let turn = emptyTurn();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const pushed = pushSse(buffer, decoder.decode(value, { stream: true }));
    buffer = pushed.buffer;
    for (const event of pushed.events) {
      turn = reduceTurn(turn, event);
      onTurn(turn);
    }
  }
  return turn;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string") return message;
    }
  } catch {
    /* not JSON */
  }
  return "Chat is unavailable right now.";
}
