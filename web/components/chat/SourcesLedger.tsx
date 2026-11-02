import type { ToolUse } from "@/lib/chat";

export function humanToolName(name: string): string {
  const words = name.replaceAll("_", " ").trim();
  if (!words) return name;
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function SourcesLedger({ tools }: { tools: ToolUse[] }) {
  if (tools.length === 0) return null;
  return (
    <div className="chat-ledger">
      <p className="kicker">Sources</p>
      <ul>
        {tools.map((tool) => (
          <li key={`${tool.name}-${tool.args_brief}`}>
            <span className="chat-ledger-name">{humanToolName(tool.name)}</span>
            {tool.args_brief ? <span className="chat-ledger-args">{tool.args_brief}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
