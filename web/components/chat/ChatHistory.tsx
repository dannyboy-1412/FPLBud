"use client";

import { useState } from "react";
import { deleteChatHistory, deleteChatMemory } from "@/lib/server/actions";

type MemoryRow = { key: string; value: string };

export function ChatHistory({ memory, note }: { memory: MemoryRow[]; note: string | null }) {
  const [gone, setGone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <section className="grid gap-3 max-w-xl mt-10" aria-labelledby="chat-history-heading">
      <h2 id="chat-history-heading">Chat</h2>
      {note ? <p className="text-ink-soft">{note}</p> : null}
      {note == null && memory.length === 0 ? (
        <p className="text-ink-soft">No saved preferences.</p>
      ) : null}
      {note == null && memory.length > 0 ? (
        <ul className="grid gap-2">
          {memory.map((row) => (
            <li key={row.key} className="flex flex-wrap items-center gap-3">
              <span>
                {row.key}: {row.value}
              </span>
              <form action={deleteChatMemory}>
                <input type="hidden" name="key" value={row.key} />
                <button type="submit" className="btn btn-secondary">
                  Remove
                </button>
              </form>
            </li>
          ))}
        </ul>
      ) : null}
      <button
        type="button"
        className="btn btn-secondary w-full sm:w-auto"
        onClick={() => {
          if (!window.confirm("Delete every chat thread and saved preference?")) return;
          void deleteChatHistory().then((result) => {
            if (result.error) setError(result.error);
            else setGone(true);
          });
        }}
      >
        Delete my chat history
      </button>
      {gone ? <p className="kicker">Chat history deleted.</p> : null}
      {error ? (
        <p className="text-vermilion-ink" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
