"use client";

import { useActionState, useEffect, useTransition } from "react";
import { useRouter } from "next/navigation";
import { TeamIdInput } from "@/components/programme/TeamIdInput";
import { lookupTeam, type LookupState } from "@/lib/server/actions";
import { teamIdErrorMessage } from "@/lib/team-id";

const idle: LookupState = { status: "idle" };

export function LandingLookup() {
  const router = useRouter();
  const [state, action] = useActionState(lookupTeam, idle);
  const [, startTransition] = useTransition();

  useEffect(() => {
    if (state.status !== "ok") return;
    startTransition(() => {
      router.push(`/try/${state.team.entry_id}`);
    });
  }, [state, router]);

  const error = state.status === "error" ? teamIdErrorMessage(state.error) : null;
  return <TeamIdInput action={action} error={error} />;
}
