export type Citation = {
  player_id: number;
  name: string;
  team?: string | null;
  price_m?: number | null;
};

export type ToolUse = { name: string; args_brief: string };

export type ParsedEvent = { name: string; data: Record<string, unknown> };

export type LiveTurn = {
  draft: string;
  finalText: string | null;
  round: number | null;
  attempt: number | null;
  phase: string | null;
  toolLabel: string | null;
  citations: Citation[];
  toolsUsed: ToolUse[];
  grounding: string | null;
  dataAsOf: string | null;
  disclaimers: string[];
  error: string | null;
  turnsLeft: number | null;
  done: boolean;
  messageId: number | null;
  proposal: { id: number; key: string; value: string; label: string } | null;
};

export function emptyTurn(): LiveTurn {
  return {
    draft: "",
    finalText: null,
    round: null,
    attempt: null,
    phase: null,
    toolLabel: null,
    citations: [],
    toolsUsed: [],
    grounding: null,
    dataAsOf: null,
    disclaimers: [],
    error: null,
    turnsLeft: null,
    done: false,
    messageId: null,
    proposal: null,
  };
}

export function pushSse(buffer: string, chunk: string): { events: ParsedEvent[]; buffer: string } {
  const text = (buffer + chunk).replace(/\r\n/g, "\n");
  const parts = text.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: ParsedEvent[] = [];
  for (const part of parts) {
    const parsed = parseBlock(part);
    if (parsed) events.push(parsed);
  }
  return { events, buffer: rest };
}

export function parseBlock(block: string): ParsedEvent | null {
  const lines = block.split("\n");
  if (lines.every((line) => line.trim() === "" || line.startsWith(":"))) return null;
  let name = "";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!name || dataLines.length === 0) return null;
  try {
    const data = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
    return { name, data };
  } catch {
    return null;
  }
}

export function reduceTurn(state: LiveTurn, event: ParsedEvent): LiveTurn {
  const data = event.data;
  if (event.name === "status") {
    return { ...state, phase: stringOf(data.phase) };
  }
  if (event.name === "tool.start") {
    return { ...state, phase: "tool", toolLabel: stringOf(data.label) };
  }
  if (event.name === "tool.end") {
    return { ...state, toolLabel: null };
  }
  if (event.name === "message.delta") {
    const round = numberOf(data.round);
    const attempt = numberOf(data.attempt) ?? 1;
    const same = state.round === round && state.attempt === attempt;
    return {
      ...state,
      round,
      attempt,
      draft: (same ? state.draft : "") + stringOf(data.text),
    };
  }
  if (event.name === "message.final") {
    return {
      ...state,
      draft: "",
      finalText: stringOf(data.text),
      citations: citationsOf(data.citations),
      toolsUsed: toolsOf(data.tools_used),
      grounding: stringOf(data.grounding),
      dataAsOf: data.data_as_of == null ? null : stringOf(data.data_as_of),
      disclaimers: stringsOf(data.disclaimers),
      messageId: numberOf(data.message_id),
    };
  }
  if (event.name === "usage") {
    return { ...state, turnsLeft: numberOf(data.turns_left_today) };
  }
  if (event.name === "error") {
    return { ...state, error: stringOf(data.message), draft: "" };
  }
  if (event.name === "done") {
    return { ...state, done: true };
  }
  if (event.name === "memory.proposal") {
    return {
      ...state,
      proposal: {
        id: numberOf(data.proposal_id) ?? 0,
        key: stringOf(data.key),
        value: stringOf(data.value),
        label: stringOf(data.label),
      },
    };
  }
  return state;
}

function stringOf(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function numberOf(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function stringsOf(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function citationsOf(value: unknown): Citation[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    if (typeof row.player_id !== "number" || typeof row.name !== "string") return [];
    return [
      {
        player_id: row.player_id,
        name: row.name,
        team: typeof row.team === "string" ? row.team : null,
        price_m: typeof row.price_m === "number" ? row.price_m : null,
      },
    ];
  });
}

function toolsOf(value: unknown): ToolUse[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    if (typeof row.name !== "string") return [];
    return [{ name: row.name, args_brief: typeof row.args_brief === "string" ? row.args_brief : "" }];
  });
}
