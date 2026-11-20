import type { Weights } from "@/lib/api";
import { getInsights, getMyTeam, getOwnedIds, getPositionLeaders } from "@/lib/server/data";
import { loadAccount, renderApi } from "@/lib/server/render-api";
import { InsightsView } from "./InsightsView";
import { ProjectionMethod } from "./ProjectionMethod";
import { boardFrom, positionFrom, type BoardId, type PositionId } from "./insights-view";

export async function InsightsSection({
  searchParams,
}: {
  searchParams: PageProps<"/dashboard/insights">["searchParams"];
}) {
  const [account, params] = await Promise.all([loadAccount(), searchParams]);
  if (!account.ok) return null;
  return renderApi(() =>
    loadInsights(
      positionFrom(params.pos),
      boardFrom(params.board),
      account.me.profile.weights,
      account.meta?.metric_labels,
    ),
  );
}

async function loadInsights(
  position: PositionId | undefined,
  board: BoardId,
  weights: Weights,
  labels: Record<string, string> | undefined,
) {
  const [team, leaders, insights, ownedIds] = await Promise.all([
    getMyTeam(),
    getPositionLeaders(),
    getInsights(position),
    getOwnedIds(),
  ]);
  return (
    <InsightsView
      key={`${position ?? "all"}:${board}`}
      position={position}
      board={board}
      hasTeam={team != null}
      squadSort={team?.sort_out}
      squadKeep={team?.leave_alone}
      leaders={leaders}
      insights={insights}
      ownedIds={ownedIds}
    >
      <ProjectionMethod weights={weights} labels={labels} />
    </InsightsView>
  );
}
