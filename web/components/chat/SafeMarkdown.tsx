import { PlayerChip } from "@/components/chat/PlayerChip";
import type { Citation } from "@/lib/chat";

const TOKEN = /(\[\[p:\d+\|[^\]]+\]\]|\*\*[^*]+\*\*)/g;

export function SafeMarkdown({ text, citations }: { text: string; citations: Citation[] }) {
  const blocks = text.split(/\n\n+/);
  return (
    <div className="grid gap-3">
      {blocks.map((block, index) => {
        const lines = block.split("\n");
        if (lines.every((line) => line.startsWith("- "))) {
          return (
            <ul key={index} className="list-disc pl-5">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>
                  <Inline text={line.slice(2)} citations={citations} />
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={index} className="whitespace-pre-wrap">
            {lines.map((line, lineIndex) => (
              <span key={lineIndex}>
                {lineIndex > 0 ? <br /> : null}
                <Inline text={line} citations={citations} />
              </span>
            ))}
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
          return <strong key={index}>{part.slice(2, -2)}</strong>;
        }
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}
