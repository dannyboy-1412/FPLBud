"use client";

import { useEffect, type FormEvent, type RefObject } from "react";
import { ArrowUp, Stop } from "@phosphor-icons/react";

const MAX = 1500;
const COUNTER_AT = 1200;
const MAX_HEIGHT = 192;

export function Composer({
  inputRef,
  value,
  busy,
  onChange,
  onSend,
  onStop,
}: {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  busy: boolean;
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

  function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    onSend();
  }

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
          placeholder="Ask the desk…"
          aria-describedby="chat-privacy"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (!busy) onSend();
            }
          }}
        />
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
      <div className="chat-composer-meta">
        <p id="chat-privacy" className="caption">
          Questions stay on your account. Enter sends. Shift+Enter adds a line.
        </p>
        {value.length > COUNTER_AT ? (
          <span className="chat-count nums">
            {value.length}/{MAX}
          </span>
        ) : null}
      </div>
    </form>
  );
}
