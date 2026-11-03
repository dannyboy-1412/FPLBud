"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { NotePencil, SidebarSimple, Trash, X } from "@phosphor-icons/react";
import { threadBucket, type ThreadBucket } from "@/components/chat/stamps";
import type { StoredThread } from "@/lib/chat";
import { deleteChatThread } from "@/lib/server/actions";

const GROUPS: { id: ThreadBucket; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "week", label: "This week" },
  { id: "earlier", label: "Earlier" },
];

export function ThreadRail({
  threads,
  activeId,
  open,
  drawer,
  collapsed,
  canStart,
  onClose,
  onToggle,
  onNew,
  onDeleted,
}: {
  threads: StoredThread[];
  activeId: string | null;
  open: boolean;
  drawer: boolean;
  collapsed: boolean;
  canStart: boolean;
  onClose: () => void;
  onToggle: () => void;
  onNew: () => void;
  onDeleted: (id: string) => void;
}) {
  const newRef = useRef<HTMLButtonElement>(null);
  const [shortcut, setShortcut] = useState("Ctrl+Shift+O");
  const grouped = GROUPS.map((group) => ({
    ...group,
    threads: threads.filter((thread) => threadBucket(thread.updated_at) === group.id),
  })).filter((group) => group.threads.length > 0);

  useEffect(() => {
    if (open) newRef.current?.focus();
  }, [open]);

  useEffect(() => {
    const apple = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
    setShortcut(apple ? "⌘⇧O" : "Ctrl+Shift+O");
  }, []);

  const className = ["chat-rail", open ? "is-open" : "", collapsed ? "is-collapsed" : ""].filter(Boolean).join(" ");

  return (
    <aside id="chat-notebook" className={className} aria-label="Chats">
      <div className="chat-rail-head">
        {collapsed ? null : <p className="chat-rail-label">Chats</p>}
        {drawer ? (
          <button type="button" className="chat-rail-close" onClick={onClose}>
            <X size={16} weight="bold" />
            Close
          </button>
        ) : (
          <button
            type="button"
            className="chat-rail-toggle"
            aria-label={collapsed ? "Expand chats" : "Collapse chats"}
            onClick={onToggle}
          >
            <SidebarSimple size={18} />
          </button>
        )}
      </div>
      <button
        ref={newRef}
        type="button"
        className="chat-new"
        onClick={onNew}
        disabled={!canStart}
        aria-label="New chat"
        title="New chat"
      >
        <NotePencil size={18} weight="bold" />
        {collapsed ? null : (
          <>
            <span>New chat</span>
            <kbd>{shortcut}</kbd>
          </>
        )}
      </button>
      {collapsed ? null : (
        <div className="chat-rail-list">
          {grouped.map((group) => (
            <section key={group.id} aria-label={group.label}>
              <h2 className="chat-group-label">{group.label}</h2>
              <ul>
                {group.threads.map((thread) => (
                  <ThreadRow
                    key={thread.id}
                    thread={thread}
                    active={thread.id === activeId}
                    onClose={onClose}
                    onDeleted={onDeleted}
                  />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </aside>
  );
}

function ThreadRow({
  thread,
  active,
  onClose,
  onDeleted,
}: {
  thread: StoredThread;
  active: boolean;
  onClose: () => void;
  onDeleted: (id: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const title = thread.title?.trim() || "Untitled";

  if (confirming) {
    return (
      <li className="chat-thread is-confirm">
        <p>Delete this chat?</p>
        <div className="chat-confirm-actions">
          <button type="button" className="chat-quiet" onClick={() => setConfirming(false)} disabled={pending}>
            Keep
          </button>
          <button type="button" className="chat-retry is-danger" onClick={() => void remove()} disabled={pending}>
            {pending ? "Deleting" : "Delete"}
          </button>
        </div>
        {error ? (
          <p className="text-vermilion-ink" role="alert">
            {error}
          </p>
        ) : null}
      </li>
    );
  }

  return (
    <li className={active ? "chat-thread is-active" : "chat-thread"}>
      {active ? (
        <span className="chat-thread-link" aria-current="page">
          <span className="chat-thread-title">{title}</span>
        </span>
      ) : (
        <Link href={`/chat?t=${thread.id}`} className="chat-thread-link" onClick={onClose}>
          <span className="chat-thread-title">{title}</span>
        </Link>
      )}
      <button
        type="button"
        className="chat-thread-delete"
        aria-label={`Delete ${title}`}
        onClick={() => {
          setError(null);
          setConfirming(true);
        }}
      >
        <Trash size={14} />
      </button>
    </li>
  );

  async function remove() {
    setPending(true);
    const result = await deleteChatThread(thread.id);
    if (result.error) {
      setPending(false);
      setError(result.error);
      return;
    }
    onDeleted(thread.id);
  }
}
