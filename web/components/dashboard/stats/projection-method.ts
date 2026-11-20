import type { Weights } from "@/lib/api";

export const BLEND_ORDER = ["xgi", "form", "fixture", "value", "minutes", "home", "trend"] as const;

export const DEFAULT_BLEND: Weights = {
  form: 0.3,
  fixture: 0.25,
  home: 0.1,
  xgi: 0.35,
  value: 0.15,
  minutes: 0.15,
  trend: 0,
};

export const BLEND_LABELS: Record<keyof Weights, string> = {
  form: "Form",
  fixture: "Fixture",
  home: "Home",
  xgi: "Expected stats",
  value: "Value",
  minutes: "Minutes",
  trend: "Price trend",
};

export const BLEND_COPY: Record<keyof Weights, string> = {
  form: "Recent points blended with FPL's form rating, ranked against the same position.",
  fixture: "Official difficulty blended with the opponent's recent expected goals.",
  home: "Whether this week's game is at home.",
  xgi: "Expected goals and assists, shrunk toward the position average and ranked against the same position. Defenders and goalkeepers also get clean-sheet value.",
  value: "Points per game for each million of price, ranked against the same position.",
  minutes: "How often they have started lately, and how much of those matches they played.",
  trend: "Transfer momentum and recent price movement.",
};

export type BlendShare = {
  key: keyof Weights;
  pct: number;
};

function weightOrDefault(weights: Partial<Weights>, key: keyof Weights): number {
  const raw = weights[key];
  if (raw == null) return DEFAULT_BLEND[key];
  const value = Math.max(Number(raw), 0);
  return Number.isFinite(value) ? value : 0;
}

function positiveWeights(weights: Partial<Weights> | null | undefined): Weights | null {
  if (!weights) return null;
  const next = { ...DEFAULT_BLEND };
  let total = 0;
  for (const key of BLEND_ORDER) {
    next[key] = weightOrDefault(weights, key);
    total += next[key];
  }
  return total > 0 ? next : null;
}

/** Shares of the blend, largest first, summing to 100. Missing keys keep the defaults; an all-zero set falls back to them. */
export function blendShares(weights: Partial<Weights> | null | undefined): BlendShare[] {
  const source = positiveWeights(weights) ?? DEFAULT_BLEND;
  const total = BLEND_ORDER.reduce((sum, key) => sum + source[key], 0);
  const drafts = BLEND_ORDER.flatMap((key) => {
    if (source[key] <= 0) return [];
    const exact = (source[key] / total) * 100;
    const floor = Math.floor(exact + 1e-9);
    return [{ key, pct: floor, frac: exact - floor }];
  });
  let leftover = 100 - drafts.reduce((sum, item) => sum + item.pct, 0);
  const byRemainder = [...drafts].sort(
    (a, b) => b.frac - a.frac || BLEND_ORDER.indexOf(a.key) - BLEND_ORDER.indexOf(b.key),
  );
  for (const item of byRemainder) {
    if (leftover <= 0) break;
    item.pct += 1;
    leftover -= 1;
  }
  return drafts
    .map(({ key, pct }) => ({ key, pct }))
    .sort((a, b) => b.pct - a.pct || BLEND_ORDER.indexOf(a.key) - BLEND_ORDER.indexOf(b.key));
}

export function blendInk(index: number, count: number): string {
  const end = 42;
  const step = count <= 1 ? 0 : (100 - end) / (count - 1);
  return `color-mix(in srgb, var(--ink) ${Math.round(100 - index * step)}%, var(--paper))`;
}
