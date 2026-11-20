import { describe, expect, it } from "vitest";
import { blendShares, DEFAULT_BLEND } from "./projection-method";

describe("blend shares", () => {
  it("turns the default weights into shares that add up to 100", () => {
    const shares = blendShares(DEFAULT_BLEND);
    expect(shares.map((part) => [part.key, part.pct])).toEqual([
      ["xgi", 27],
      ["form", 23],
      ["fixture", 19],
      ["value", 12],
      ["minutes", 11],
      ["home", 8],
    ]);
    expect(shares.reduce((sum, part) => sum + part.pct, 0)).toBe(100);
  });

  it("drops a weight of zero and falls back when nothing is set", () => {
    expect(blendShares({ ...DEFAULT_BLEND, trend: 0 }).some((part) => part.key === "trend")).toBe(false);
    expect(blendShares({ form: 0, fixture: 0, home: 0, xgi: 0, value: 0, minutes: 0, trend: 0 })).toEqual(
      blendShares(DEFAULT_BLEND),
    );
    expect(blendShares(null)).toEqual(blendShares(DEFAULT_BLEND));
  });

  it("gives the whole blend to a single ingredient", () => {
    expect(blendShares({ xgi: 1 })).toEqual([{ key: "xgi", pct: 100 }]);
  });
});
