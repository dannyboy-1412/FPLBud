import type { Weights } from "@/lib/api";
import {
  BLEND_COPY,
  BLEND_LABELS,
  blendInk,
  blendShares,
} from "./projection-method";

const FACTORS = [
  {
    name: "Games",
    detail: "A blank week scores 0. A double gameweek counts twice.",
  },
  {
    name: "Chance",
    detail: "FPL's chance of playing this week. An unavailable player scores 0.",
  },
  {
    name: "Minutes",
    detail:
      "How much of the match they are likely to play. No minutes this season scores 0. Minutes also sit in the blend, so a rotation risk is counted twice.",
  },
] as const;

export function ProjectionMethod({
  weights,
  labels,
}: {
  weights: Weights;
  labels?: Record<string, string> | null;
}) {
  const shares = blendShares(weights);
  const trendIncluded = shares.some((part) => part.key === "trend");

  return (
    <section className="proj-method" aria-labelledby="proj-method-title">
      <h2 id="proj-method-title" className="proj-title">
        How a projected point is made
      </h2>
      <p className="proj-lead">
        The figures above are expected points for the next gameweek. One game, a full chance of playing and a
        certain start puts a player between 1 and 7.
      </p>
      <div className="proj-sum">
        <p className="proj-equation">
          <span>points</span>
          <span className="proj-op">=</span>
          <span>games</span>
          <span className="proj-op">×</span>
          <span>chance</span>
          <span className="proj-op">×</span>
          <span>minutes</span>
          <span className="proj-op">×</span>
          <span className="proj-term">
            (1 <span className="proj-op">+</span> 6 <span className="proj-op">×</span> blend)
          </span>
        </p>
        <div className="proj-scale">
          <div className="proj-scale-end">
            <span className="proj-scale-num">1</span>
            <span className="proj-scale-caption">Weak blend</span>
          </div>
          <div className="proj-scale-track" />
          <div className="proj-scale-end is-end">
            <span className="proj-scale-num">7</span>
            <span className="proj-scale-caption">Perfect blend</span>
          </div>
        </div>
        <p className="proj-scale-note">One game, available, and certain to start.</p>
      </div>

      <div className="proj-body">
        <dl className="proj-factors">
          {FACTORS.map((factor) => (
            <div key={factor.name}>
              <dt>{factor.name}</dt>
              <dd>{factor.detail}</dd>
            </div>
          ))}
        </dl>

        <div>
          <h3 className="proj-subhead">Your blend</h3>
          <div className="proj-bar" aria-hidden="true">
            {shares.map((part, index) => (
              <span key={part.key} style={{ flex: part.pct, background: blendInk(index, shares.length) }} />
            ))}
          </div>
          <ul className="proj-blend">
            {shares.map((part, index) => (
              <li key={part.key}>
                <span className="proj-swatch" style={{ background: blendInk(index, shares.length) }} aria-hidden="true" />
                <span className="proj-name">{labels?.[part.key] || BLEND_LABELS[part.key]}</span>
                <span className="proj-pct">{part.pct}%</span>
                <span className="proj-desc">{BLEND_COPY[part.key]}</span>
              </li>
            ))}
          </ul>
          <p className="proj-aside">
            Form, expected stats and value ignore anyone without an appearance in the last five rounds.
            {trendIncluded ? "" : " Price trend is left out of this blend."}
          </p>
        </div>
      </div>
    </section>
  );
}
