"use client";

import { catchError, type ErrorInfo } from "next/error";

function Fallback(_props: object, { error, retry }: ErrorInfo) {
  const message = error instanceof Error ? error.message : "We can't reach the press room right now.";
  return (
    <div className="py-6">
      <p className="kicker">Correction</p>
      <p className="text-claret mt-2">Something went wrong</p>
      <p className="caption mt-1">{message}</p>
      <button type="button" className="btn btn-secondary mt-3" onClick={() => retry()}>
        Try again
      </button>
    </div>
  );
}

export default catchError(Fallback);
