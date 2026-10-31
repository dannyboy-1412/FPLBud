import type { ToolUse } from "@/lib/chat";

export function HowIGotThis({ tools }: { tools: ToolUse[] }) {
  if (tools.length === 0) return null;
  return (
    <details className="text-ink-soft">
      <summary>How I got this</summary>
      <ul className="mt-2 grid gap-1">
        {tools.map((tool) => (
          <li key={`${tool.name}-${tool.args_brief}`}>
            {tool.name}
            {tool.args_brief ? ` ${tool.args_brief}` : ""}
          </li>
        ))}
      </ul>
    </details>
  );
}
