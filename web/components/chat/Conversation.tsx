"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown, Chats, SidebarSimple } from "@phosphor-icons/react";
import { AssistantAnswer } from "@/components/chat/AssistantAnswer";
import { EmptyBriefing } from "@/components/chat/EmptyBriefing";
import { LiveAnswer } from "@/components/chat/LiveAnswer";
import { ProposalCard } from "@/components/chat/ProposalCard";
import { UserNote } from "@/components/chat/UserNote";
import type { BriefingEvent, BriefingSquad } from "@/components/chat/briefing";
import type { ChatBubble, LiveTurn } from "@/lib/chat";

export function Conversation({
  title,
  bubbles,
  live,
  busy,
  event,
  missing,
  teamPromise,
  onRetry,
  onOpenNotebook,
  onExpand,
}: {
  title: string;
  bubbles: ChatBubble[];
  live: LiveTurn;
  busy: boolean;
  event: BriefingEvent;
  missing: boolean;
  teamPromise: Promise<BriefingSquad | null>;
  onRetry: () => void;
  onOpenNotebook: (() => void) | null;
  onExpand: (() => void) | null;
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const [away, setAway] = useState(false);
  const showLive = busy || Boolean(live.draft) || Boolean(live.error);
  const showBriefing = bubbles.length === 0 && !showLive;
  const canRetry = bubbles.some((message) => message.role === "user");
  const showTop = !showBriefing || onOpenNotebook != null || onExpand != null;
  const latestAssistant = showLive ? -1 : findLastAssistant(bubbles);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || !stickRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [bubbles, live.draft, live.steps, live.error, busy]);

  function onScroll() {
    const el = scrollerRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const stuck = distance < 80;
    stickRef.current = stuck;
    setAway(!stuck);
  }

  function jump() {
    const el = scrollerRef.current;
    if (!el) return;
    stickRef.current = true;
    setAway(false);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }

  return (
    <section className="chat-conversation" aria-label="Conversation">
      {showTop ? (
        <header className="chat-top">
          {onOpenNotebook ? (
            <button type="button" id="chat-open-notebook" className="chat-notebook" aria-controls="chat-notebook" onClick={onOpenNotebook}>
              <Chats size={16} weight="bold" />
              Chats
            </button>
          ) : null}
          {onExpand ? (
            <button type="button" className="chat-expand" aria-label="Expand chats" onClick={onExpand}>
              <SidebarSimple size={18} />
            </button>
          ) : null}
          {showBriefing ? null : <h1 className="chat-title">{title}</h1>}
        </header>
      ) : null}
      <div className="chat-scroll" ref={scrollerRef} onScroll={onScroll}>
        <div className="chat-stream">
          {showBriefing ? <EmptyBriefing teamPromise={teamPromise} event={event} missing={missing} /> : null}
          {bubbles.map((message, index) =>
            message.role === "user" ? (
              <UserNote key={`${message.role}-${message.createdAt}-${index}`} message={message} arrive={index === bubbles.length - 1} />
            ) : (
              <AssistantAnswer
                key={`${message.role}-${message.messageId ?? index}`}
                message={message}
                latest={index === latestAssistant}
                arrive={index === bubbles.length - 1}
              />
            ),
          )}
          {showLive ? <LiveAnswer live={live} busy={busy} onRetry={canRetry ? onRetry : null} /> : null}
          {live.proposal ? <ProposalCard proposal={live.proposal} /> : null}
        </div>
        {away ? (
          <button type="button" className="chat-jump" aria-label="Jump to latest" onClick={jump}>
            <ArrowDown size={16} weight="bold" />
          </button>
        ) : null}
      </div>
    </section>
  );
}

function findLastAssistant(bubbles: ChatBubble[]): number {
  for (let index = bubbles.length - 1; index >= 0; index -= 1) {
    if (bubbles[index]?.role === "assistant") return index;
  }
  return -1;
}
