const STAGES = [
  { id: "context", label: "Reading your team sheet" },
  { id: "horizon_1", label: "Next gameweek" },
  { id: "horizon_3", label: "Next 3 gameweeks" },
  { id: "horizon_5", label: "Next 5 gameweeks" },
  { id: "chips", label: "Chip check" },
  { id: "explain", label: "Writing it up" },
];

export function GoingToPress({
  stage,
  progress,
  error,
  stalled,
  onRetry,
}: {
  stage?: string | null;
  progress: number;
  error?: string | null;
  stalled?: boolean;
  onRetry?: () => void;
}) {
  const current = STAGES.findIndex((s) => s.id === stage);
  return (
    <div role="status" aria-live="polite">
      <p className="kicker mb-3">Going to press</p>
      <div className="h-0.5 bg-rule mb-6">
        <div className="h-0.5 bg-ink" style={{ width: `${progress}%` }} />
      </div>
      <ol className="list-none p-0 m-0 space-y-3">
        {STAGES.map((s, i) => {
          const done = current > i || progress >= 100;
          const here = current === i;
          return (
            <li key={s.id} className={done ? "" : here ? "font-semibold" : "text-ink-faint"}>
              <span className={here ? "text-vermilion" : ""}>{done ? "✓" : here ? "●" : "○"}</span> {s.label}
            </li>
          );
        })}
      </ol>
      {stalled && !error ? <p className="caption mt-4">Taking longer than usual</p> : null}
      {error ? (
        <div className="mt-6">
          <p className="text-claret">Something went wrong</p>
          <p className="caption">{error}</p>
          {onRetry ? (
            <button type="button" className="btn btn-secondary mt-3" onClick={onRetry}>
              Try again
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
