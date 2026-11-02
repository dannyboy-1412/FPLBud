export type Citation = {
  player_id: number;
  name: string;
  team?: string | null;
  price_m?: number | null;
};

export type ToolUse = { name: string; args_brief: string };

export type ParsedEvent = { name: string; data: Record<string, unknown> };

export type WorkStep = { label: string; done: boolean };

export type LiveTurn = {
  draft: string;
  finalText: string | null;
  round: number | null;
  attempt: number | null;
  phase: string | null;
  toolLabel: string | null;
  steps: WorkStep[];
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

export type StoredThread = {
  id: string;
  title: string | null;
  message_count: number;
  updated_at: string | null;
};

export type StoredMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  feedback: 1 | -1 | null;
  created_at: string | null;
};

export type ChatBubble = {
  role: "user" | "assistant";
  text: string;
  citations: Citation[];
  toolsUsed: ToolUse[];
  dataAsOf: string | null;
  messageId: number | null;
  disclaimers: string[];
  createdAt: string | null;
  feedback: 1 | -1 | null;
  stopped: boolean;
  steps: WorkStep[];
};

export type ChatUsage = {
  turns_used: number;
  turns_left: number;
  daily_cap: number;
  optimiser_calls: number;
  resets_at: string;
};

const CHECKING_LABEL = "Checking the answer";

export function emptyTurn(): LiveTurn {
  return {
    draft: "",
    finalText: null,
    round: null,
    attempt: null,
    phase: null,
    toolLabel: null,
    steps: [],
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
    const phase = stringOf(data.phase);
    if (phase !== "checking") return { ...state, phase };
    const alreadyOpen = state.steps.some((step) => !step.done && step.label === CHECKING_LABEL);
    if (alreadyOpen) return { ...state, phase };
    return { ...state, phase, steps: appendStep(state.steps, CHECKING_LABEL) };
  }
  if (event.name === "tool.start") {
    const label = stringOf(data.label);
    return {
      ...state,
      phase: "tool",
      toolLabel: label || null,
      steps: label ? appendStep(state.steps, label) : finishSteps(state.steps),
    };
  }
  if (event.name === "tool.end") {
    return { ...state, toolLabel: null, steps: finishSteps(state.steps) };
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
      steps: finishSteps(state.steps),
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

function finishSteps(steps: WorkStep[]): WorkStep[] {
  if (steps.every((step) => step.done)) return steps;
  return steps.map((step) => (step.done ? step : { label: step.label, done: true }));
}

function appendStep(steps: WorkStep[], label: string): WorkStep[] {
  return [...finishSteps(steps), { label, done: false }];
}

export function plainChatText(text: string): string {
  return text.replace(/\[\[p:\d+\|([^\]]+)\]\]/g, "$1").replace(/\*\*([^*]+)\*\*/g, "$1");
}

export function threadFrom(value: unknown): StoredThread | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  if (typeof row.id !== "string") return null;
  return {
    id: row.id,
    title: typeof row.title === "string" ? row.title : null,
    message_count: typeof row.message_count === "number" ? row.message_count : 0,
    updated_at: typeof row.updated_at === "string" ? row.updated_at : null,
  };
}

export function messageFrom(value: unknown): StoredMessage | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  if (typeof row.id !== "number") return null;
  if (row.role !== "user" && row.role !== "assistant") return null;
  return {
    id: row.id,
    role: row.role,
    content: typeof row.content === "string" ? row.content : "",
    citations: citationsOf(row.citations),
    feedback: row.feedback === 1 || row.feedback === -1 ? row.feedback : null,
    created_at: typeof row.created_at === "string" ? row.created_at : null,
  };
}

export function usageFrom(value: unknown): ChatUsage | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  if (typeof row.turns_left !== "number" || typeof row.daily_cap !== "number") return null;
  return {
    turns_used: typeof row.turns_used === "number" ? row.turns_used : 0,
    turns_left: row.turns_left,
    daily_cap: row.daily_cap,
    optimiser_calls: typeof row.optimiser_calls === "number" ? row.optimiser_calls : 0,
    resets_at: typeof row.resets_at === "string" ? row.resets_at : "00:00 UTC",
  };
}

export function bubbleFromStored(message: StoredMessage): ChatBubble {
  return {
    role: message.role,
    text: message.content,
    citations: message.citations,
    toolsUsed: [],
    dataAsOf: null,
    messageId: message.role === "assistant" ? message.id : null,
    disclaimers: [],
    createdAt: message.created_at,
    feedback: message.feedback,
    stopped: false,
    steps: [],
  };
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
