import { describe, expect, it } from "vitest";
import { clockTime, threadBucket } from "./stamps";

describe("chat stamps", () => {
  const sunday = new Date("2026-11-01T12:00:00Z");

  it("groups a thread by the London calendar", () => {
    expect(threadBucket("2026-11-01T08:00:00Z", sunday)).toBe("today");
    expect(threadBucket("2026-10-31T12:00:00Z", sunday)).toBe("week");
    expect(threadBucket("2026-10-20T12:00:00Z", sunday)).toBe("earlier");
    expect(threadBucket("2026-06-01T23:30:00Z", new Date("2026-06-02T10:00:00Z"))).toBe("today");
  });

  it("prints the clock in London", () => {
    expect(clockTime("2026-11-01T18:30:00Z")).toBe("18:30");
    expect(clockTime("2026-06-01T23:30:00Z")).toBe("00:30");
  });
});
