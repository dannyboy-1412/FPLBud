"use client";

import { useEffect, useState, useTransition } from "react";
import { Trash } from "@phosphor-icons/react";
import { formatMemoryKey } from "@/components/programme/settings-model";
import { deleteChatHistory, deleteChatMemory } from "@/lib/server/actions";

type MemoryRow = { key: string; value: string };

export function ChatHistory({ memory, note }: { memory: MemoryRow[]; note: string | null }) {
  const [items, setItems] = useState<MemoryRow[]>(memory);
  const [removingKey, setRemovingKey] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [cleared, setCleared] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clearing, startClear] = useTransition();
  const [removing, startRemove] = useTransition();

  useEffect(() => {
    setItems(memory);
  }, [memory]);

  function handleRemove(key: string) {
    setError(null);
    setRemovingKey(key);
    const formData = new FormData();
    formData.set("key", key);
    startRemove(async () => {
      try {
        await deleteChatMemory(formData);
        setItems((current) => current.filter((row) => row.key !== key));
      } catch {
        setError("Could not remove that preference. Try again.");
      } finally {
        setRemovingKey(null);
      }
    });
  }

  function handleClearHistory() {
    setError(null);
    startClear(async () => {
      const result = await deleteChatHistory();
      if (result.error) {
        setError(result.error);
        return;
      }
      setItems([]);
      setConfirmClear(false);
      setCleared(true);
    });
  }

  return (
    <section className="settings-chapter" aria-labelledby="chat-history-heading">
      <div className="settings-aside">
        <h2 id="chat-history-heading" className="settings-heading">
          Assistant
        </h2>
        <p className="settings-copy">
          Preferences the assistant remembered from your chats, plus your saved conversations.
        </p>
      </div>

      <div className="settings-panel settings-assistant-stack">
        <div className="settings-memory-block">
          <p className="settings-row-title">Remembered preferences</p>
          {note ? <p className="settings-row-note">{note}</p> : null}
          {note == null && items.length === 0 ? (
            <p className="settings-row-note">
              No saved preferences yet. When you ask the assistant to remember how you play, it
              shows up here.
            </p>
          ) : null}
          {note == null && items.length > 0 ? (
            <ul className="settings-memory-list">
              {items.map((row) => {
                const busy = removing && removingKey === row.key;
                return (
                  <li key={row.key} className="settings-memory-item">
                    <div className="settings-memory-text">
                      <span className="settings-memory-key">{formatMemoryKey(row.key)}</span>
                      <span className="settings-memory-val">{row.value}</span>
                    </div>
                    <button
                      type="button"
                      className="settings-memory-remove"
                      disabled={busy}
                      onClick={() => handleRemove(row.key)}
                    >
                      {busy ? "Removing..." : "Remove"}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>

        <div className="settings-history-row">
          <div>
            <p className="settings-row-title">Conversation history</p>
            <p className="settings-row-note">
              Remove every chat thread and remembered preference.
            </p>
          </div>
          {!confirmClear ? (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={clearing}
              onClick={() => {
                setCleared(false);
                setError(null);
                setConfirmClear(true);
              }}
            >
              <Trash size={16} weight="bold" aria-hidden="true" />
              Clear chat history
            </button>
          ) : null}
        </div>

        {confirmClear ? (
          <div className="settings-inline-confirm" role="alertdialog" aria-label="Confirm clearing chat history">
            <p className="settings-inline-confirm-copy">
              Delete every chat thread and saved preference? This cannot be undone.
            </p>
            <div className="settings-inline-confirm-actions">
              <button
                type="button"
                className="btn btn-destructive"
                disabled={clearing}
                onClick={handleClearHistory}
              >
                {clearing ? "Clearing..." : "Delete history"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={clearing}
                onClick={() => setConfirmClear(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : null}

        {cleared ? (
          <p className="settings-status-ok" aria-live="polite">
            Chat history cleared.
          </p>
        ) : null}
        {error ? (
          <p className="settings-status-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
