"use client";

import { use } from "react";
import { Pitch } from "@/components/programme/Pitch";
import { useEdition } from "@/components/dashboard/EditionProvider";
import type { AgentRun, PublicTeam } from "@/lib/api";

export function PitchWithIncoming({
  team,
  runPromise,
}: {
  team: PublicTeam;
  runPromise: Promise<AgentRun | null>;
}) {
  const { tab, optimisticRun } = useEdition();
  const serverRun = use(runPromise);
  const run = optimisticRun ?? serverRun;
  const plan = run?.results?.[tab];
  return <Pitch team={team} incomingIds={plan?.transfers.map((tr) => tr.in) ?? []} />;
}
