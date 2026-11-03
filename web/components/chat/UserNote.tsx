import { clockTime } from "@/components/chat/stamps";
import type { ChatBubble } from "@/lib/chat";

export function UserNote({ message, arrive }: { message: ChatBubble; arrive: boolean }) {
  const time = clockTime(message.createdAt);
  return (
    <article className={arrive ? "chat-note chat-arrive" : "chat-note"}>
      <p>{message.text}</p>
      {time ? <time dateTime={message.createdAt ?? undefined}>{time}</time> : null}
    </article>
  );
}
