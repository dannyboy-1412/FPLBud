import { describe, expect, it } from "vitest";
import type { Weights } from "@/lib/api";
import {
  formatMemoryKey,
  hasUnsavedSettings,
  hitLimitNote,
  METRIC_ORDER,
  metricShares,
  metricTotal,
  weightsEqual,
} from "./settings-model";

const DEFAULTS: Weights = {
  form: 0.3,
  fixture: 0.25,
  home: 0.1,
  xgi: 0.35,
  value: 0.15,
  minutes: 0.15,
  trend: 0,
};

describe("metricShares", () => {
  it("sums active percentages to 100 using largest-remainder rounding", () => {
    const shares = metricShares(DEFAULTS);
    const sum = METRIC_ORDER.reduce((acc, key) => acc + shares[key], 0);
    expect(sum).toBe(100);
    expect(shares.trend).toBe(0);
    expect(shares.xgi).toBeGreaterThan(shares.form);
  });

  it("handles equal thirds without rounding drift", () => {
    const equal: Weights = {
      form: 0.5,
      fixture: 0.5,
      home: 0.5,
      xgi: 0,
      value: 0,
      minutes: 0,
      trend: 0,
    };
    const shares = metricShares(equal);
    expect(shares.form + shares.fixture + shares.home).toBe(100);
    expect(shares.form).toBe(34);
    expect(shares.fixture).toBe(33);
    expect(shares.home).toBe(33);
  });

  it("returns zeros across the board when every weight is zero", () => {
    const zero: Weights = {
      form: 0,
      fixture: 0,
      home: 0,
      xgi: 0,
      value: 0,
      minutes: 0,
      trend: 0,
    };
    expect(metricTotal(zero)).toBe(0);
    expect(metricShares(zero)).toEqual(zero);
  });
});

describe("settings dirty checks", () => {
  it("treats floating-point equivalent weights as equal", () => {
    const slightlyOff: Weights = { ...DEFAULTS, form: 0.1 + 0.2 };
    expect(weightsEqual(DEFAULTS, slightlyOff)).toBe(true);
  });

  it("detects changes to weights, horizon, or max hits", () => {
    const saved = { weights: DEFAULTS, default_horizon: 3, max_hits: 1 };
    expect(hasUnsavedSettings({ ...saved, weights: { ...DEFAULTS } }, saved)).toBe(false);
    expect(hasUnsavedSettings({ ...saved, default_horizon: 5 }, saved)).toBe(true);
    expect(hasUnsavedSettings({ ...saved, max_hits: 0 }, saved)).toBe(true);
    expect(hasUnsavedSettings({ ...saved, weights: { ...DEFAULTS, trend: 0.15 } }, saved)).toBe(true);
  });
});

describe("copy helpers", () => {
  it("explains hit limits in plain terms", () => {
    expect(hitLimitNote(0)).toBe("Free transfers only");
    expect(hitLimitNote(1)).toBe("Up to 1 extra transfer (-4 pts)");
    expect(hitLimitNote(2)).toBe("Up to 2 extra transfers (-8 pts)");
  });

  it("formats snake_case memory keys into sentence case", () => {
    expect(formatMemoryKey("captain_style")).toBe("Captain style");
    expect(formatMemoryKey("avoid-hits")).toBe("Avoid hits");
  });
});
