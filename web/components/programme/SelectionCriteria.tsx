"use client";

import type { Weights } from "@/lib/api";

const ORDER: (keyof Weights)[] = ["form", "fixture", "home", "xgi", "value", "minutes", "trend"];
const OPTIONAL = new Set(["value", "minutes", "trend"]);

export function SelectionCriteria({
  weights,
  labels,
  descriptions,
  disabled,
  onChange,
}: {
  weights: Weights;
  labels: Record<string, string>;
  descriptions: Record<string, string>;
  disabled?: boolean;
  onChange?: (next: Weights) => void;
}) {
  const total = ORDER.reduce((s, k) => s + Math.max(weights[k], 0), 0) || 1;
  return (
    <div className={`relative ${disabled ? "opacity-40" : ""}`}>
      <div className="flex h-4 my-3 border border-ink">
        {ORDER.filter((k) => weights[k] > 0).map((k, i) => (
          <span
            key={k}
            title={labels[k]}
            style={{
              flex: weights[k],
              background: ["#161412", "#4A453E", "#8C857A", "#BDB4A1", "#5E574B", "#3A352C", "#CFC6B4"][i],
            }}
          />
        ))}
      </div>
      {ORDER.map((key) => (
        <div key={key} className="grid grid-cols-[180px_1fr_48px] gap-4 items-center py-3 border-b border-rule">
          <div>
            <p className="font-semibold">{labels[key] ?? key}</p>
            <p className="caption">{descriptions[key]}</p>
            {OPTIONAL.has(key) ? (
              <label className="caption">
                <input
                  type="checkbox"
                  className="mr-1"
                  checked={weights[key] > 0}
                  disabled={disabled}
                  onChange={(e) =>
                    onChange?.({ ...weights, [key]: e.target.checked ? 0.15 : 0 })
                  }
                />
                Include
              </label>
            ) : null}
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={weights[key]}
            disabled={disabled}
            onChange={(e) => onChange?.({ ...weights, [key]: Number(e.target.value) })}
            className="w-full accent-vermilion"
          />
          <span className="stat text-right">{Math.round((weights[key] / total) * 100)}%</span>
        </div>
      ))}
      {disabled ? (
        <div className="absolute inset-0 grid place-items-center bg-[rgba(244,239,228,0.6)]">
          <p className="caption bg-paper-bright border border-ink shadow-[6px_6px_0_#161412] p-6">
            Sign in with Google to set your own criteria.
          </p>
        </div>
      ) : null}
    </div>
  );
}
