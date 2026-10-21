"use client";

import { useActionState, useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { TeamIdInput } from "@/components/programme/TeamIdInput";
import { lookupTeam, saveTeam, type LookupState, type SaveTeamState } from "@/lib/server/actions";
import { teamIdErrorMessage } from "@/lib/team-id";

const idleLookup: LookupState = { status: "idle" };
const idleSave: SaveTeamState = {};

function SaveButton() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className="btn btn-primary mt-4" disabled={pending}>
      {pending ? "Filing your team..." : "This is my team"}
    </button>
  );
}

export function OnboardingForm() {
  const [lookup, lookupAction] = useActionState(lookupTeam, idleLookup);
  const [save, saveAction] = useActionState(saveTeam, idleSave);
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    setDismissed(false);
  }, [lookup]);
  const error = lookup.status === "error" ? teamIdErrorMessage(lookup.error) : null;
  const preview = lookup.status === "ok" && !dismissed ? lookup.team : null;

  return (
    <>
      <div className="mt-8 max-w-xl">
        <TeamIdInput action={lookupAction} error={error} />
      </div>
      {preview ? (
        <div className="mt-8 border border-ink p-6 max-w-xl">
          <p className="kicker">Confirmation slip</p>
          <h2 className="mt-2">{preview.name}</h2>
          <p className="caption">{preview.manager}</p>
          {preview.overall_rank ? <p className="stat mt-2">{preview.overall_rank.toLocaleString()}</p> : null}
          <form action={saveAction}>
            <input type="hidden" name="entryId" value={preview.entry_id} />
            <SaveButton />
            <button type="button" className="btn btn-text ml-4" onClick={() => setDismissed(true)}>
              Not you? Try again
            </button>
          </form>
          {save.error ? <p className="caption text-claret mt-3">{save.error}</p> : null}
        </div>
      ) : null}
    </>
  );
}
