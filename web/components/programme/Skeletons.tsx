import { PitchMarkings } from "@/components/programme/Pitch";

const SHIRT =
  "M10 5.5 14.2 2.2h7.6L26 5.5 33.2 8.4 29.4 13.2 26 11.4V28H10V11.4L6.6 13.2 2.8 8.4Z";

function GhostPlayer({ delay }: { delay: number }) {
  const shift = { animationDelay: `${delay}ms` };
  return (
    <div className="pitch-card is-ghost">
      <svg className="pitch-shirt" width="36" height="32" viewBox="0 0 36 32" aria-hidden style={shift}>
        <path className="pitch-ghost-kit" d={SHIRT} />
        <path className="pitch-ghost-neck" d="M14.2 2.6c1.2 2.6 2.4 3.8 3.8 3.8s2.6-1.2 3.8-3.8" fill="none" />
      </svg>
      <span className="pitch-plate pitch-ghost-plate">
        <span className="pitch-ghost-bar is-name" style={shift} />
        <span className="pitch-ghost-bar is-club" style={shift} />
        <span className="pitch-ghost-bar is-opp" style={shift} />
      </span>
    </div>
  );
}

export function HeadingSkeleton() {
  return (
    <div className="mb-6">
      <div className="skeleton h-3 w-28 mb-3" />
      <div className="skeleton h-10 w-64" />
    </div>
  );
}

export function PitchSkeleton() {
  const rows = [1, 4, 4, 2];
  return (
    <div className="pitch-unit" aria-hidden>
      <div className="pitch">
        <PitchMarkings />
        <div className="pitch-rows">
          {rows.map((count, row) => {
            const start = rows.slice(0, row).reduce((sum, size) => sum + size, 0);
            return (
              <div key={row} className="pitch-row">
                {Array.from({ length: count }, (_, index) => (
                  <GhostPlayer key={start + index} delay={(start + index) * 90} />
                ))}
              </div>
            );
          })}
        </div>
      </div>
      <div className="pitch-subs">
        <p className="kicker">Substitutes</p>
        <div className="pitch-row">
          {Array.from({ length: 4 }, (_, index) => (
            <GhostPlayer key={index} delay={(11 + index) * 90} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function TeamViewSkeleton() {
  return (
    <div aria-hidden>
      <div className="skeleton h-3 w-32 mb-2" />
      <div className="skeleton h-10 w-64 mb-6" />
      <div className="skeleton h-16 w-40 mb-8" />
      <PitchSkeleton />
      <StatsSkeleton />
    </div>
  );
}

export function TeamPitchSkeleton() {
  return (
    <div aria-hidden>
      <div className="skeleton h-3 w-32 mb-2" />
      <div className="skeleton h-16 w-40 mb-8" />
      <PitchSkeleton />
    </div>
  );
}

export function TableSkeleton() {
  return (
    <div className="space-y-2" aria-hidden>
      {Array.from({ length: 12 }, (_, i) => (
        <div key={i} className="skeleton h-11 w-full" />
      ))}
    </div>
  );
}

export function SettingsSkeleton() {
  return (
    <div className="mt-8 space-y-4" aria-hidden>
      <div className="skeleton h-3 w-40" />
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="skeleton h-16 w-full" />
      ))}
    </div>
  );
}

export function StatsSkeleton() {
  return (
    <div className="grid md:grid-cols-2 gap-x-12 gap-y-8 mt-4" aria-hidden>
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="space-y-2">
          <div className="skeleton h-3 w-28 mb-3" />
          {Array.from({ length: 6 }, (_, j) => (
            <div key={j} className="skeleton h-11 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}
