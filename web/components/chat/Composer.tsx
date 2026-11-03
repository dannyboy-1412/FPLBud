"use client";

import { Suspense, use, useEffect, type FormEvent, type RefObject } from "react";
import { ArrowUp, Stop } from "@phosphor-icons/react";
import type { BriefingEvent, BriefingSquad } from "@/components/chat/briefing";

const MAX = 1500;
const COUNTER_AT = 1200;
const MAX_HEIGHT = 192;
const LOW_AT = 3;

export function Composer({
  inputRef,
  value,
  busy,
  turnsLeft,
  event,
  teamPromise,
  onChange,
  onSend,
  onStop,
}: {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  busy: boolean;
  turnsLeft: number | null;
  event: BriefingEvent;
  teamPromise: Promise<BriefingSquad | null>;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
}) {
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [inputRef, value]);

  function submit(formEvent: FormEvent) {
    formEvent.preventDefault();
    if (busy) return;
    onSend();
  }

  const low = turnsLeft != null && turnsLeft <= LOW_AT;

  return (
    <form className="chat-composer" onSubmit={submit}>
      <div className="chat-notepad">
        <label className="sr-only" htmlFor="chat-question">
          Question
        </label>
        <textarea
          id="chat-question"
          ref={inputRef}
          rows={1}
          value={value}
          maxLength={MAX}
          placeholder="Ask about your team, a player, or this gameweek…"
          title="Enter to send. Shift+Enter for a new line."
          aria-describedby="chat-disclaimer"
          onChange={(change) => onChange(change.target.value)}
          onKeyDown={(keyEvent) => {
            if (keyEvent.key === "Enter" && !keyEvent.shiftKey) {
              keyEvent.preventDefault();
              if (!busy) onSend();
            }
          }}
        />
        <div className="chat-toolbar">
          <Suspense fallback={<ContextChip event={event} squad={false} />}>
            <ResolvedContext teamPromise={teamPromise} event={event} />
          </Suspense>
          <button
            type={busy ? "button" : "submit"}
            className={busy ? "chat-send is-stop" : "chat-send"}
            disabled={!busy && !value.trim()}
            aria-label={busy ? "Stop" : "Ask"}
            onClick={busy ? onStop : undefined}
          >
            {busy ? <Stop size={14} weight="fill" /> : <ArrowUp size={16} weight="bold" />}
          </button>
        </div>
      </div>
      <p id="chat-disclaimer" className="chat-disclaimer">
        FPLBud can make mistakes. Check before the deadline.
        {turnsLeft != null ? (
          <>
            {" "}
            · <span className={low ? "is-low" : undefined}>{questionsLeft(turnsLeft)}</span>
          </>
        ) : null}
        {value.length > COUNTER_AT ? <span className="chat-count"> {value.length}/{MAX}</span> : null}
      </p>
    </form>
  );
}

function ResolvedContext({ teamPromise, event }: { teamPromise: Promise<BriefingSquad | null>; event: BriefingEvent }) {
  const team = use(teamPromise);
  return <ContextChip event={event} squad={team != null} />;
}

function ContextChip({ event, squad }: { event: BriefingEvent; squad: boolean }) {
  const label = [event ? `GW${event.id}` : null, squad ? "My squad" : null].filter(Boolean).join(" · ");
  if (!label) return <span />;
  return <span className="chat-context">{label}</span>;
}

function questionsLeft(left: number): string {
  return left === 1 ? "1 question left today" : `${left} questions left today`;
}
