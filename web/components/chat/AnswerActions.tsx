"use client";

import { useState } from "react";
import { Books, Check, Copy, ThumbsDown, ThumbsUp } from "@phosphor-icons/react";
import { SourcesLedger } from "@/components/chat/SourcesLedger";
import { plainChatText, type ToolUse } from "@/lib/chat";
import { sendChatFeedback } from "@/lib/server/actions";

export function AnswerActions({
  text,
  messageId,
  feedback,
  tools,
}: {
  text: string;
  messageId: number | null;
  feedback: 1 | -1 | null;
  tools: ToolUse[];
}) {
  const [copied, setCopied] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(feedback === 1 ? "up" : feedback === -1 ? "down" : null);
  const [sources, setSources] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className={sources ? "chat-actions is-open" : "chat-actions"}>
      <div className="chat-action-row">
        <button type="button" className="chat-icon-btn" aria-label={copied ? "Copied" : "Copy"} onClick={() => void copy()}>
          {copied ? <Check size={16} weight="bold" /> : <Copy size={16} />}
        </button>
        {messageId != null ? (
          <>
            <button
              type="button"
              className="chat-icon-btn"
              aria-label="Useful"
              aria-pressed={vote === "up"}
              onClick={() => void choose(1)}
            >
              <ThumbsUp size={16} weight={vote === "up" ? "fill" : "regular"} />
            </button>
            <button
              type="button"
              className="chat-icon-btn"
              aria-label="Not useful"
              aria-pressed={vote === "down"}
              onClick={() => void choose(-1)}
            >
              <ThumbsDown size={16} weight={vote === "down" ? "fill" : "regular"} />
            </button>
          </>
        ) : null}
        {tools.length > 0 ? (
          <button
            type="button"
            className="chat-icon-btn"
            aria-label="Sources"
            aria-expanded={sources}
            onClick={() => setSources((open) => !open)}
          >
            <Books size={16} weight={sources ? "fill" : "regular"} />
          </button>
        ) : null}
      </div>
      {error ? (
        <p className="text-vermilion-ink" role="alert">
          {error}
        </p>
      ) : null}
      {sources ? <SourcesLedger tools={tools} /> : null}
    </div>
  );

  async function copy() {
    try {
      await navigator.clipboard.writeText(plainChatText(text));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
      setError("Could not copy that.");
    }
  }

  async function choose(value: 1 | -1) {
    if (messageId == null) return;
    if ((value === 1 && vote === "up") || (value === -1 && vote === "down")) return;
    const result = await sendChatFeedback(messageId, value);
    if (result.error) {
      setError(result.error);
      return;
    }
    setError(null);
    setVote(value === 1 ? "up" : "down");
  }
}
