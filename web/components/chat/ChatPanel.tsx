"use client";

import { useState, type FormEvent } from "react";
import { HowIGotThis } from "@/components/chat/HowIGotThis";
import { SafeMarkdown } from "@/components/chat/SafeMarkdown";
import { confirmChatMemory, sendChatFeedback } from "@/lib/server/actions";
import {
  emptyTurn,
  pushSse,
  reduceTurn,
  type Citation,
  type LiveTurn,
  type ToolUse,
} from "@/lib/chat";

const PROMPTS = ["When is the deadline?", "Who should I captain?", "Is a hit worth it?"];

type Bubble = {
  role: "user" | "assistant";
  text: string;
  citations: Citation[];
  toolsUsed: ToolUse[];
  dataAsOf: string | null;
  messageId: number | null;
  disclaimers: string[];
};

export function ChatPanel() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Bubble[]>([]);
  const [live, setLive] = useState<LiveTurn>(emptyTurn);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask(text: string) {
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((current) => [
      ...current,
      {
        role: "user",
        text,
        citations: [],
        toolsUsed: [],
        dataAsOf: null,
        messageId: null,
        disclaimers: [],
      },
    ]);
    setLive(emptyTurn());
    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          thread_id: threadId,
          client_msg_id: crypto.randomUUID(),
        }),
      });
      const nextThread = response.headers.get("X-FPLBud-Thread");
      if (nextThread) setThreadId(nextThread);
      if (!response.ok || !response.body) {
        const detail = await readError(response);
        setLive({ ...emptyTurn(), error: detail, done: true });
        return;
      }
      const finished = await readStream(response.body, setLive);
      if (finished.finalText) {
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            text: finished.finalText ?? "",
            citations: finished.citations,
            toolsUsed: finished.toolsUsed,
            dataAsOf: finished.dataAsOf,
            messageId: finished.messageId,
            disclaimers: finished.disclaimers,
          },
        ]);
        setLive({ ...emptyTurn(), turnsLeft: finished.turnsLeft, proposal: finished.proposal });
      } else {
        setLive(finished);
      }
    } catch {
      setLive({ ...emptyTurn(), error: "Chat is unavailable right now.", done: true });
    } finally {
      setBusy(false);
    }
  }

  function send(event: FormEvent) {
    event.preventDefault();
    void ask(input.trim());
  }

  return (
    <div className="grid gap-6 max-w-3xl">
      <div className="grid gap-4 min-h-48" aria-live="polite">
        {messages.length === 0 && !busy ? (
          <div className="grid gap-3">
            <p className="text-ink-soft">Ask about your squad, a player, or the deadline.</p>
            <div className="flex flex-wrap gap-2">
              {PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void ask(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        {messages.map((message, index) => (
          <MessageBlock key={`${message.role}-${index}`} message={message} />
        ))}
        {busy && live.draft ? (
          <p className="whitespace-pre-wrap" aria-hidden>
            {live.draft}
          </p>
        ) : null}
        {live.toolLabel ? <p className="kicker">{live.toolLabel}</p> : null}
        {live.phase === "checking" ? <p className="kicker">Checking the answer</p> : null}
        {live.error ? (
          <p className="text-vermilion-ink" role="alert">
            {live.error}
          </p>
        ) : null}
        {live.proposal ? <ProposalCard proposal={live.proposal} /> : null}
      </div>
      <form onSubmit={send} className="grid gap-3">
        <label className="kicker" htmlFor="chat-question">
          Question
        </label>
        <textarea
          id="chat-question"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          rows={3}
          maxLength={1500}
          disabled={busy}
          className="w-full bg-paper-bright border border-rule p-3 text-ink"
          placeholder="Who should I captain?"
          aria-describedby="chat-privacy"
        />
        <p id="chat-privacy" className="text-ink-soft">
          Questions stay on your account. You can delete them in Settings.
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <button type="submit" className="btn btn-primary" disabled={busy || !input.trim()}>
            {busy ? "Thinking" : "Ask"}
          </button>
          {live.turnsLeft != null ? (
            <span className="kicker">{live.turnsLeft} left today</span>
          ) : null}
        </div>
      </form>
    </div>
  );
}

function MessageBlock({ message }: { message: Bubble }) {
  if (message.role === "user") {
    return <p className="font-medium">{message.text}</p>;
  }
  return (
    <div className="grid gap-2">
      <SafeMarkdown text={message.text} citations={message.citations} />
      {message.disclaimers.map((line) => (
        <p key={line} className="text-ink-soft">
          {line}
        </p>
      ))}
      {message.dataAsOf ? <p className="kicker">Data as of {message.dataAsOf}</p> : null}
      <HowIGotThis tools={message.toolsUsed} />
      {message.messageId != null ? <Feedback messageId={message.messageId} /> : null}
    </div>
  );
}

function Feedback({ messageId }: { messageId: number }) {
  const [sent, setSent] = useState<"up" | "down" | null>(null);
  if (sent) return <p className="kicker">Thanks, that was recorded.</p>;
  return (
    <div className="flex gap-2">
      <button type="button" className="btn btn-secondary" onClick={() => void vote(messageId, 1, setSent)}>
        Useful
      </button>
      <button type="button" className="btn btn-secondary" onClick={() => void vote(messageId, -1, setSent)}>
        Not useful
      </button>
    </div>
  );
}

async function vote(
  messageId: number,
  value: 1 | -1,
  setSent: (value: "up" | "down") => void,
) {
  const result = await sendChatFeedback(messageId, value);
  if (!result.error) setSent(value === 1 ? "up" : "down");
}

function ProposalCard({
  proposal,
}: {
  proposal: { id: number; key: string; value: string; label: string };
}) {
  const [state, setState] = useState<"open" | "saved" | "dismissed">("open");
  if (state !== "open") {
    return <p className="kicker">{state === "saved" ? "Saved." : "Dismissed."}</p>;
  }
  return (
    <div className="border border-rule p-3 grid gap-2" role="region" aria-label="Save a preference">
      <p>
        Save {proposal.label}: {proposal.value}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void decide(proposal.id, true, setState)}
        >
          Save
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => void decide(proposal.id, false, setState)}
        >
          Not now
        </button>
      </div>
    </div>
  );
}

async function decide(
  proposalId: number,
  accept: boolean,
  setState: (value: "saved" | "dismissed") => void,
) {
  const result = await confirmChatMemory(proposalId, accept);
  if (!result.error) setState(accept ? "saved" : "dismissed");
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
