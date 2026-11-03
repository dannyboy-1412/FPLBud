import { describe, expect, it } from "vitest";
import { greetingName, squadPrompts, statusLine, type BriefingSquad } from "./briefing";

const event = { id: 10, name: "Gameweek 10", deadline_time: "2026-11-06T18:30:00Z" };
const morning = new Date("2026-11-04T08:00:00Z");

function player(
  webName: string,
  extras: Partial<BriefingSquad["squad_players"][number]> = {},
): BriefingSquad["squad_players"][number] {
  return {
    web_name: webName,
    status: "a",
    chance_of_playing_next_round: 100,
    is_captain: false,
    is_vice_captain: false,
    ...extras,
  };
}

function squad(overrides: Partial<BriefingSquad> = {}): BriefingSquad {
  return {
    manager: "Danny Jones",
    bank: 4,
    free_transfers: 1,
    chips_available: [{ name: "bboost" }],
    squad_players: [
      player("Haaland", { is_captain: true }),
      player("Salah", { is_vice_captain: true }),
      player("Saka", { status: "d", chance_of_playing_next_round: 25 }),
      player("Watkins", { status: "d", chance_of_playing_next_round: 75 }),
    ],
    ...overrides,
  };
}

describe("chat briefing", () => {
  it("greets the manager by the London part of day", () => {
    expect(greetingName(squad(), event, morning)).toBe("Morning, Danny");
    expect(greetingName(squad(), event, new Date("2026-11-04T20:00:00Z"))).toBe("Evening, Danny");
    expect(greetingName(squad(), event, new Date("2026-06-01T11:00:00Z"))).toBe("Afternoon, Danny");
    expect(greetingName(squad(), event, new Date("2026-11-04T23:30:00Z"))).toBe("Hello, Danny");
  });

  it("falls back when there is no manager name", () => {
    expect(greetingName(null, event, morning)).toBe("Ready for Gameweek 10?");
    expect(greetingName(squad({ manager: "  " }), event, morning)).toBe("Ready for Gameweek 10?");
    expect(greetingName(null, null, morning)).toBe("The desk is open");
  });

  it("builds one status line from the deadline and the squad", () => {
    expect(statusLine(squad(), event, new Date("2026-11-04T00:00:00Z"))).toBe(
      "GW10 deadline Fri 6 Nov, 18:30 · 2d 18h left · 1 free transfer · £0.4m · 2 flagged",
    );
  });

  it("omits squad facts when the team has not loaded", () => {
    expect(statusLine(null, event, new Date("2026-11-06T12:00:00Z"))).toBe(
      "GW10 deadline Fri 6 Nov, 18:30 · 6h 30m left",
    );
  });

  it("names the captain, the biggest doubt, the bank and the chip", () => {
    expect(squadPrompts(squad()).map((prompt) => prompt.question)).toEqual([
      "Captain Haaland or Salah?",
      "Is Saka likely to start?",
      "Replace Saka with £0.4m?",
      "Play my Bench Boost this week?",
    ]);
  });

  it("uses generic prompts when the squad has nothing to name", () => {
    const quiet = squad({
      bank: 0,
      chips_available: [],
      squad_players: [player("Haaland", { is_captain: true }), player("Salah")],
    });
    expect(squadPrompts(quiet).map((prompt) => prompt.question)).toEqual([
      "Who should I captain?",
      "Which of my players have the best fixtures?",
      "Is a hit worth it?",
      "Should I use a chip this week?",
    ]);
    expect(squadPrompts(null).map((prompt) => prompt.question)).toEqual([
      "Who should I captain?",
      "Is a hit worth it?",
      "Should I use a chip this week?",
      "Which of my players have the best fixtures?",
    ]);
  });
});
