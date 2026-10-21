"use client";

import { FormEvent, useState } from "react";
import { useFormStatus } from "react-dom";
function SubmitIcon({ pending }: { pending: boolean }) {
  if (pending) {
    return (
      <span className="inline-block w-[22px] h-[22px] border-2 border-paper-bright border-t-transparent rounded-full animate-spin" />
    );
  }
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="square" />
    </svg>
  );
}
import { parseTeamId } from "@/lib/team-id";

function Fields({
  value,
  error,
  onChange,
}: {
  value: string;
  error?: string | null;
  onChange: (value: string) => void;
}) {
  const { pending } = useFormStatus();
  const helpId = "team-id-help";
  return (
    <>
      <div className="flex-1">
        <label className="kicker block mb-2" htmlFor="team-id">
          Your FPL team ID
        </label>
        <input
          id="team-id"
          name="teamId"
          inputMode="numeric"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="1234567"
          aria-invalid={Boolean(error)}
          aria-describedby={helpId}
          className={`w-full h-16 border-0 border-b-2 bg-transparent font-[family-name:var(--font-fraunces)] text-[2rem] font-semibold nums px-1 outline-none ${error ? "border-claret" : "border-ink"}`}
        />
        {error ? (
          <p id={helpId} role="alert" className="caption text-claret mt-2">
            {error}
          </p>
        ) : (
          <p id={helpId} className="caption mt-2 help-id">
            It&apos;s the number in the address bar on your FPL Points page:
            fantasy.premierleague.com/entry/<mark className="bg-ochre-tint px-0.5">1234567</mark>/event/6
          </p>
        )}
      </div>
      <button className="btn btn-primary btn-square" type="submit" disabled={pending} aria-label="Look up team">
        <SubmitIcon pending={pending} />
      </button>
    </>
  );
}

export function TeamIdInput({
  action,
  error,
}: {
  action: (formData: FormData) => void;
  error?: string | null;
}) {
  const [value, setValue] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const shown = localError ?? error;

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    const parsed = parseTeamId(value);
    if (!parsed.ok) {
      e.preventDefault();
      setLocalError(
        parsed.reason === "empty"
          ? "Enter your team ID"
          : "That doesn't look like a team ID; it's the number in your Points page URL.",
      );
    }
  }

  return (
    <form className="id-field flex items-end gap-3" action={action} onSubmit={handleSubmit}>
      <Fields
        value={value}
        error={shown}
        onChange={(next) => {
          setValue(next);
          setLocalError(null);
        }}
      />
    </form>
  );
}
