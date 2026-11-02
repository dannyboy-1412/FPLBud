import type { ReactNode } from "react";
import { PlayerChip } from "@/components/chat/PlayerChip";
import type { Citation } from "@/lib/chat";

const TOKEN = /(\[\[p:\d+\|[^\]]+\]\]|\*\*[^*]+\*\*)/g;

export function SafeMarkdown({
  text,
  citations,
  trailing,
}: {
  text: string;
  citations: Citation[];
  trailing?: ReactNode;
}) {
  const blocks = text.split(/\n\n+/).filter((block) => block.length > 0);
  if (blocks.length === 0) {
    return trailing ? <div className="chat-column">{trailing}</div> : null;
  }
  return (
    <div className="chat-column">
      {blocks.map((block, index) => {
        const end = index === blocks.length - 1 ? trailing : null;
        const lines = block.split("\n");
        if (lines.every((line) => line.startsWith("- "))) {
          return (
            <div key={index}>
              <ul className="chat-list">
                {lines.map((line, lineIndex) => (
                  <li key={lineIndex}>
                    <Inline text={line.slice(2)} citations={citations} />
                  </li>
                ))}
              </ul>
              {end}
            </div>
          );
        }
        return (
          <p key={index}>
            {lines.map((line, lineIndex) => (
              <span key={lineIndex}>
                {lineIndex > 0 ? <br /> : null}
                <Inline text={line} citations={citations} />
              </span>
            ))}
            {end}
          </p>
        );
      })}
    </div>
  );
}

function Inline({ text, citations }: { text: string; citations: Citation[] }) {
  const parts = text.split(TOKEN);
  return (
    <>
      {parts.map((part, index) => {
        const markup = /^\[\[p:(\d+)\|([^\]]+)\]\]$/.exec(part);
        if (markup) {
          const playerId = Number(markup[1]);
          const known = citations.find((item) => item.player_id === playerId);
          return (
            <PlayerChip
              key={index}
              citation={known ?? { player_id: playerId, name: markup[2] ?? "" }}
            />
          );
        }
        if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
          return (
            <strong key={index} className="chat-strong">
              {part.slice(2, -2)}
            </strong>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}
