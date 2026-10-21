import { Suspense } from "react";
import { PlayersChrome } from "@/components/players/PlayersChrome";
import { PlayersRows } from "@/components/players/PlayersRows";
import { TableSkeleton } from "@/components/programme/Skeletons";
import SectionError from "@/components/programme/SectionError";
import { getPlayers, type PlayerFilters } from "@/lib/server/data";

export default function PlayersPage({ searchParams }: PageProps<"/players">) {
  return (
    <>
      <h1>Players</h1>
      <p className="caption mt-2">Ranked by default criteria. Sign in to use your own.</p>
      <Suspense fallback={<TableSkeleton />}>
        <SectionError>
          <PlayersWithParams searchParams={searchParams} />
        </SectionError>
      </Suspense>
    </>
  );
}

function parseFilters(sp: { position?: string | string[]; max_cost?: string | string[]; horizon?: string | string[] }): PlayerFilters {
  const one = (value?: string | string[]) => (Array.isArray(value) ? value[0] : value);
  const position = Number(one(sp.position));
  const maxCost = Number(one(sp.max_cost));
  const horizon = Number(one(sp.horizon));
  return {
    position: position >= 1 && position <= 4 ? position : undefined,
    maxCost: maxCost >= 35 && maxCost <= 150 ? maxCost : 150,
    horizon: horizon >= 1 && horizon <= 6 ? horizon : 1,
  };
}

async function PlayersWithParams({ searchParams }: { searchParams: PageProps<"/players">["searchParams"] }) {
  const filters = parseFilters(await searchParams);
  const key = `${filters.position ?? ""}-${filters.maxCost}-${filters.horizon}`;
  return (
    <PlayersChrome filters={filters}>
      <Suspense key={key} fallback={<TableSkeleton />}>
        <PlayersTable filters={filters} />
      </Suspense>
    </PlayersChrome>
  );
}

async function PlayersTable({ filters }: { filters: PlayerFilters }) {
  const data = await getPlayers(filters);
  return <PlayersRows rows={data.players} />;
}
