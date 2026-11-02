"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown, Notebook } from "@phosphor-icons/react";
import { AssistantAnswer } from "@/components/chat/AssistantAnswer";
import { EmptyBriefing } from "@/components/chat/EmptyBriefing";
import { LiveAnswer } from "@/components/chat/LiveAnswer";
import { ProposalCard } from "@/components/chat/ProposalCard";
import { UserNote } from "@/components/chat/UserNote";
import type { ChatBubble, LiveTurn } from "@/lib/chat";

export function Conversation({
  title,
  bubbles,
  live,
  busy,
  turnsLeft,
  dailyCap,
  event,
  missing,
  onAsk,
  onRetry,
  onOpenNotebook,
}: {
  title: string;
  bubbles: ChatBubble[];
  live: LiveTurn;
  busy: boolean;
  turnsLeft: number | null;
  dailyCap: number | null;
  event: { id: number; name: string; deadline_time: string } | null;
  missing: boolean;
  onAsk: (question: string) => void;
  onRetry: () => void;
  onOpenNotebook: () => void;
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const [away, setAway] = useState(false);
  const showLive = busy || Boolean(live.draft) || Boolean(live.error);
  const showBriefing = bubbles.length === 0 && !showLive;
  const canRetry = bubbles.some((message) => message.role === "user");

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
      <header className="chat-top">
        <button
          type="button"
          id="chat-open-notebook"
          className="chat-notebook"
          aria-controls="chat-notebook"
          onClick={onOpenNotebook}
        >
          <Notebook size={16} weight="bold" />
          Notebook
        </button>
        <h1 className="chat-title">{title}</h1>
        <TurnsTally left={turnsLeft} cap={dailyCap} />
      </header>
      <div className="chat-scroll" ref={scrollerRef} onScroll={onScroll}>
        <div className="chat-stream">
          {showBriefing ? <EmptyBriefing event={event} missing={missing} onAsk={onAsk} /> : null}
          {bubbles.map((message, index) =>
            message.role === "user" ? (
              <UserNote key={`${message.role}-${message.createdAt}-${index}`} message={message} />
            ) : (
              <AssistantAnswer key={`${message.role}-${message.messageId ?? index}`} message={message} />
            ),
          )}
          {showLive ? <LiveAnswer live={live} busy={busy} onRetry={canRetry ? onRetry : null} /> : null}
          {live.proposal ? <ProposalCard proposal={live.proposal} /> : null}
        </div>
        {away ? (
          <button type="button" className="chat-jump" onClick={jump}>
            <ArrowDown size={14} weight="bold" />
            Jump to latest
          </button>
        ) : null}
      </div>
    </section>
  );
}

function TurnsTally({ left, cap }: { left: number | null; cap: number | null }) {
  if (left == null) return null;
  const total = cap && cap > 0 ? Math.min(cap, 16) : 0;
  const filled = cap && cap > 0 ? Math.max(0, Math.round((Math.min(Math.max(left, 0), cap) / cap) * total)) : 0;
  return (
    <p className="chat-tally">
      {total > 0 ? (
        <span className="chat-ticks" aria-hidden>
          {Array.from({ length: total }, (_, index) => (
            <span key={index} className={index < filled ? "is-left" : undefined} />
          ))}
        </span>
      ) : null}
      <span className="kicker">
        {left} left today
      </span>
    </p>
  );
}
