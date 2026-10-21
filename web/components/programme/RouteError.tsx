"use client";

export function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div>
      <p className="kicker">Correction</p>
      <h1 className="mt-2">Something went to press wrong</h1>
      <p className="caption mt-3">{error.message || "We can't reach the press room right now."}</p>
      <button type="button" className="btn btn-secondary mt-6" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
