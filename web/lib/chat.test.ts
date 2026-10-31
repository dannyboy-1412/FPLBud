import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { emptyTurn, pushSse, reduceTurn } from "./chat";

const here = dirname(fileURLToPath(import.meta.url));
const golden = readFileSync(join(here, "../../contracts/chat/sse/deadline.sse"), "utf8");

describe("chat sse", () => {
  it("reduces the golden transcript", () => {
    const parsed = pushSse("", golden);
    expect(parsed.buffer).toBe("");
    let turn = emptyTurn();
    for (const event of parsed.events) {
      turn = reduceTurn(turn, event);
    }
    expect(turn.done).toBe(true);
    expect(turn.finalText).toContain("Haaland");
    expect(turn.citations[0]?.name).toBe("Haaland");
    expect(turn.citations[0]?.price_m).toBe(15);
    expect(turn.messageId).toBe(3);
    expect(turn.turnsLeft).toBe(19);
    expect(turn.toolsUsed[0]?.name).toBe("get_gameweek_context");
    expect(turn.dataAsOf).toBe("2026-10-25T12:00:00Z");
  });

  it("resets the draft when the attempt changes", () => {
    let turn = reduceTurn(emptyTurn(), {
      name: "message.delta",
      data: { text: "old", round: 1, attempt: 1 },
    });
    turn = reduceTurn(turn, {
      name: "message.delta",
      data: { text: "new", round: 1, attempt: 2 },
    });
    expect(turn.draft).toBe("new");
  });
});
