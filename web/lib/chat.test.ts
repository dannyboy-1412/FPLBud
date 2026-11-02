import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { bubbleFromStored, emptyTurn, messageFrom, plainChatText, pushSse, reduceTurn } from "./chat";

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

  it("records working steps as tools start, finish, and the answer is checked", () => {
    let turn = reduceTurn(emptyTurn(), {
      name: "tool.start",
      data: { label: "Reading the deadline" },
    });
    expect(turn.steps).toEqual([{ label: "Reading the deadline", done: false }]);
    turn = reduceTurn(turn, { name: "tool.end", data: {} });
    expect(turn.steps).toEqual([{ label: "Reading the deadline", done: true }]);
    turn = reduceTurn(turn, {
      name: "tool.start",
      data: { label: "Checking the squad" },
    });
    turn = reduceTurn(turn, { name: "status", data: { phase: "checking" } });
    expect(turn.steps).toEqual([
      { label: "Reading the deadline", done: true },
      { label: "Checking the squad", done: true },
      { label: "Checking the answer", done: false },
    ]);
    turn = reduceTurn(turn, { name: "status", data: { phase: "checking" } });
    expect(turn.steps.filter((step) => step.label === "Checking the answer")).toHaveLength(1);
  });

  it("maps a stored answer without the live-only footers", () => {
    const stored = messageFrom({
      id: 9,
      role: "assistant",
      content: "Captain **[[p:13|Haaland]]**.",
      citations: [{ player_id: 13, name: "Haaland", team: "MCI", price_m: 15 }],
      feedback: 1,
      created_at: "2026-10-25T12:00:00Z",
    });
    expect(stored?.citations[0]?.team).toBe("MCI");
    const bubble = bubbleFromStored(stored!);
    expect(bubble.messageId).toBe(9);
    expect(bubble.feedback).toBe(1);
    expect(bubble.toolsUsed).toEqual([]);
    expect(bubble.dataAsOf).toBeNull();
    expect(plainChatText(bubble.text)).toBe("Captain Haaland.");
  });
});
