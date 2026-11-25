"use client";

import { useRef, type CSSProperties } from "react";
import type { Weights } from "@/lib/api";
import {
  METRIC_ORDER,
  metricShares,
  metricTone,
  metricTotal,
  OPTIONAL_METRICS,
  OPTIONAL_ON_WEIGHT,
} from "@/components/programme/settings-model";

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
  const remembered = useRef<Partial<Record<keyof Weights, number>>>({});
  const shares = metricShares(weights);
  const total = metricTotal(weights);
  const activeCount = METRIC_ORDER.filter((key) => weights[key] > 0).length;

  function setWeight(key: keyof Weights, nextValue: number) {
    if (nextValue > 0) {
      remembered.current[key] = nextValue;
    }
    onChange?.({ ...weights, [key]: nextValue });
  }

  function toggleOptional(key: keyof Weights) {
    if (weights[key] > 0) {
      remembered.current[key] = weights[key];
      onChange?.({ ...weights, [key]: 0 });
      return;
    }
    const restore = remembered.current[key] ?? OPTIONAL_ON_WEIGHT;
    onChange?.({ ...weights, [key]: restore });
  }

  return (
    <div className={`criteria ${disabled ? "is-disabled" : ""}`}>
      <div className="criteria-summary">
        <div
          className="criteria-bar"
          role="img"
          aria-label={`Active scoring blend across ${activeCount} signals`}
        >
          {METRIC_ORDER.filter((key) => shares[key] > 0).map((key) => (
            <span
              key={key}
              title={`${labels[key] ?? key}: ${shares[key]}%`}
              style={{ flex: shares[key], background: metricTone(key) }}
            />
          ))}
        </div>
        <p className={`criteria-summary-note ${total <= 0 ? "is-warn" : ""}`}>
          {total <= 0
            ? "Every signal is at zero. Turn up at least one signal to save."
            : `${activeCount} of ${METRIC_ORDER.length} signals active in your projected-points blend.`}
        </p>
      </div>

      <ul className="criteria-list">
        {METRIC_ORDER.map((key) => {
          const isOptional = OPTIONAL_METRICS.has(key);
          const value = weights[key];
          const active = value > 0;
          const pct = shares[key];
          const label = labels[key] ?? key;
          const fill = `${Math.round(Math.min(Math.max(value, 0), 1) * 100)}%`;

          return (
            <li key={key} className={`criteria-row ${active ? "" : "is-off"}`}>
              <div className="criteria-info">
                <div className="criteria-head">
                  <span
                    className="criteria-dot"
                    style={{ background: active ? metricTone(key) : "var(--rule)" }}
                    aria-hidden="true"
                  />
                  <label htmlFor={`weight-${key}`} className="criteria-name">
                    {label}
                  </label>
                  {isOptional ? (
                    <button
                      type="button"
                      role="switch"
                      aria-checked={active}
                      aria-label={`Include ${label}`}
                      disabled={disabled}
                      className={`criteria-switch ${active ? "is-on" : ""}`}
                      onClick={() => toggleOptional(key)}
                    >
                      <span className="criteria-switch-thumb" aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
                {descriptions[key] ? <p className="criteria-desc">{descriptions[key]}</p> : null}
              </div>

              <div className="criteria-control">
                <input
                  id={`weight-${key}`}
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={value}
                  disabled={disabled}
                  aria-valuetext={`${pct}% of blend`}
                  onChange={(e) => setWeight(key, Number(e.target.value))}
                  className="criteria-range"
                  style={{ "--fill": fill } as CSSProperties}
                />
                <span className="criteria-pct nums">{pct}%</span>
              </div>
            </li>
          );
        })}
      </ul>

      {disabled ? (
        <div className="criteria-overlay">
          <p className="criteria-overlay-note">Sign in with Google to set your own criteria.</p>
        </div>
      ) : null}
    </div>
  );
}
