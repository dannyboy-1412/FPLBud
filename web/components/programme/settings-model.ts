import type { Weights } from "@/lib/api";

export const METRIC_ORDER: (keyof Weights)[] = [
  "form",
  "fixture",
  "home",
  "xgi",
  "value",
  "minutes",
  "trend",
];

export const OPTIONAL_METRICS: ReadonlySet<keyof Weights> = new Set([
  "value",
  "minutes",
  "trend",
]);

export const OPTIONAL_ON_WEIGHT = 0.15;

export const HORIZON_OPTIONS = [
  { value: 1, label: "1 week" },
  { value: 3, label: "3 weeks" },
  { value: 5, label: "5 weeks" },
] as const;

export const MIN_HITS = 0;
export const MAX_HITS = 3;

export type PlanningSettings = {
  weights: Weights;
  default_horizon: number;
  max_hits: number;
};

export function metricTotal(weights: Weights): number {
  return METRIC_ORDER.reduce((sum, key) => sum + Math.max(weights[key], 0), 0);
}

/** Integer percentages for every metric using largest-remainder rounding so active weights sum to 100. */
export function metricShares(weights: Weights): Record<keyof Weights, number> {
  const result: Record<keyof Weights, number> = {
    form: 0,
    fixture: 0,
    home: 0,
    xgi: 0,
    value: 0,
    minutes: 0,
    trend: 0,
  };
  const total = metricTotal(weights);
  if (total <= 0) return result;

  const drafts = METRIC_ORDER.flatMap((key) => {
    const value = Math.max(weights[key], 0);
    if (value <= 0) return [];
    const exact = (value / total) * 100;
    const floor = Math.floor(exact + 1e-9);
    return [{ key, pct: floor, frac: exact - floor }];
  });

  let leftover = 100 - drafts.reduce((sum, item) => sum + item.pct, 0);
  const byRemainder = [...drafts].sort(
    (a, b) => b.frac - a.frac || METRIC_ORDER.indexOf(a.key) - METRIC_ORDER.indexOf(b.key),
  );
  for (const item of byRemainder) {
    if (leftover <= 0) break;
    item.pct += 1;
    leftover -= 1;
  }
  for (const item of drafts) {
    result[item.key] = item.pct;
  }
  return result;
}

export function weightsEqual(a: Weights, b: Weights): boolean {
  return METRIC_ORDER.every((key) => Math.abs((a[key] ?? 0) - (b[key] ?? 0)) < 1e-6);
}

export function hasUnsavedSettings(
  current: PlanningSettings,
  saved: PlanningSettings,
): boolean {
  return (
    current.default_horizon !== saved.default_horizon ||
    current.max_hits !== saved.max_hits ||
    !weightsEqual(current.weights, saved.weights)
  );
}

export function hitLimitNote(maxHits: number): string {
  if (maxHits <= 0) return "Free transfers only";
  const points = maxHits * 4;
  return maxHits === 1 ? `Up to 1 extra transfer (-${points} pts)` : `Up to ${maxHits} extra transfers (-${points} pts)`;
}

export function metricTone(key: keyof Weights): string {
  const index = METRIC_ORDER.indexOf(key);
  const ratio = 100 - Math.max(index, 0) * 10;
  return `color-mix(in srgb, var(--ink) ${ratio}%, var(--paper))`;
}

export function formatMemoryKey(key: string): string {
  const cleaned = key.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
  if (!cleaned) return key;
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}
