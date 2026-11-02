import { clockTime } from "@/components/chat/stamps";
import type { ChatBubble } from "@/lib/chat";

export function UserNote({ message }: { message: ChatBubble }) {
  const time = clockTime(message.createdAt);
  return (
    <article className="chat-note">
      <p>{message.text}</p>
      {time ? <time dateTime={message.createdAt ?? undefined}>{time}</time> : null}
    </article>
  );
}
