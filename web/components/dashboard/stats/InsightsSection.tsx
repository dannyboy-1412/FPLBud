import Link from "next/link";
import type { InsightsStats, PlayerRow, PublicTeam, SetPiecePlayer } from "@/lib/api";
import { getInsights, getMyTeam, getOwnedIds, getPositionLeaders } from "@/lib/server/data";
import { loadAccount, renderApi } from "@/lib/server/render-api";
import { POSITIONS, price } from "./format";
import { ReturnCompare } from "./ReturnCompare";
import { PlayerCell, StatTable } from "./StatTable";

const POSITION_IDS = [1, 2, 3, 4] as const;
type PositionId = (typeof POSITION_IDS)[number];

function positionFrom(raw: string | string[] | undefined): PositionId | undefined {
  const value = Array.isArray(raw) ? raw[0] : raw;
  const id = Number(value);
  return POSITION_IDS.find((position) => position === id);
}

export async function InsightsSection({
  searchParams,
}: {
  searchParams: PageProps<"/dashboard/insights">["searchParams"];
}) {
  const [account, params] = await Promise.all([loadAccount(), searchParams]);
  if (!account.ok) return null;
  return renderApi(() => loadInsights(positionFrom(params.pos)));
}

async function loadInsights(position: PositionId | undefined) {
  const [team, leaders, insights, ownedIds] = await Promise.all([
    getMyTeam(),
    getPositionLeaders(),
    getInsights(position),
    getOwnedIds(),
  ]);
  return (
    <InsightsBody
      position={position}
      team={team}
      leaders={leaders}
      insights={insights}
      ownedIds={ownedIds}
    />
  );
}

function InsightsBody({
  position,
  team,
  leaders,
  insights,
  ownedIds,
}: {
  position: PositionId | undefined;
  team: PublicTeam | null;
  leaders: Record<number, PlayerRow[]>;
  insights: InsightsStats;
  ownedIds: number[];
}) {
  const columns = position == null ? POSITIONS : POSITIONS.filter((item) => item.id === position);
  return (
    <div className="space-y-10">
      <PositionFilter position={position} />
      <div className="grid md:grid-cols-2 gap-x-12 gap-y-10">
        <section>
          <p className="kicker mb-3">Due a return</p>
          <p className="caption mb-3">
            Fewer goals and assists than their chances were worth. The points often catch up, so these are usually holds.
          </p>
          <ReturnCompare
            players={team?.underperforming}
            direction="short"
            empty="Nobody in the squad is clearly short of a return."
          />
        </section>
        <section>
          <p className="kicker mb-3">Running hot</p>
          <p className="caption mb-3">
            More goals and assists than their chances were worth. Fine to own. The extra points can cool off.
          </p>
          <ReturnCompare
            players={team?.overperforming}
            direction="ahead"
            empty="Nobody in the squad is clearly ahead of their chances."
          />
        </section>
      </div>
      <div className={columns.length === 1 ? "" : "grid md:grid-cols-2 xl:grid-cols-4 gap-x-12 gap-y-10"}>
        {columns.map((item) => (
          <section key={item.id}>
            <p className="kicker mb-3">{item.label}</p>
            <p className="caption mb-3">Top five by expected points.</p>
            <StatTable
              headers={["Player", "Proj"]}
              rows={(leaders[item.id] ?? []).map((player) => ({
                id: player.id,
                cells: [
                  <PlayerCell key="n" player={player} ownedIds={ownedIds} />,
                  player.proj.toFixed(1),
                ],
              }))}
            />
          </section>
        ))}
      </div>
      <section>
        <p className="kicker mb-3">In form</p>
        <p className="caption mb-3">Recent returns among players with enough minutes.</p>
        <StatTable
          headers={["Player", "Pts", "Form", "xGI/90"]}
          rows={insights.in_form.map((player) => ({
            id: player.id,
            cells: [
              <PlayerCell key="n" player={player} ownedIds={ownedIds} />,
              String(player.recent_points),
              player.form.toFixed(1),
              player.xgi90.toFixed(2),
            ],
          }))}
        />
      </section>
      <div className="grid md:grid-cols-2 gap-x-12 gap-y-10">
        <section>
          <p className="kicker mb-3">League, due a return</p>
          <p className="caption mb-3">
            Fewer goals and assists than their chances were worth, across the league.
          </p>
          <ReturnCompare
            players={insights.underperformers}
            direction="short"
            ownedIds={ownedIds}
            empty="Nobody in the league is clearly short of a return."
          />
        </section>
        <section>
          <p className="kicker mb-3">League, running hot</p>
          <p className="caption mb-3">
            More goals and assists than their chances were worth. The extra points can cool off.
          </p>
          <ReturnCompare
            players={insights.overperformers}
            direction="ahead"
            ownedIds={ownedIds}
            empty="Nobody in the league is clearly ahead of their chances."
          />
        </section>
      </div>
      <section>
        <p className="kicker mb-3">Differentials to buy</p>
        <p className="caption mb-3">Under 10% owned, ranked with your weights.</p>
        <StatTable
          headers={["Player", "Own%", "Proj", "Price"]}
          rows={insights.differentials.map((player) => ({
            id: player.id,
            cells: [
              <PlayerCell key="n" player={player} ownedIds={ownedIds} />,
              `${player.selected_by_percent.toFixed(1)}%`,
              player.proj.toFixed(1),
              price(player.now_cost),
            ],
          }))}
        />
      </section>
      <section>
        <p className="kicker mb-3">Defensive contributions</p>
        <p className="caption mb-3">How often they clear the FPL defensive-contribution threshold.</p>
        <StatTable
          headers={["Player", "Hit%", "DC/90", "Hits"]}
          rows={insights.defensive.map((player) => ({
            id: player.id,
            cells: [
              <PlayerCell key="n" player={player} ownedIds={ownedIds} />,
              `${Math.round(player.hit_rate * 100)}%`,
              player.dc_per_90.toFixed(1),
              `${player.dc_hits}/${player.dc_starts}`,
            ],
          }))}
        />
      </section>
      <section>
        <p className="kicker mb-3">Bonus</p>
        <p className="caption mb-3">Season bonus, bonus points per 90, and bonus per start.</p>
        <StatTable
          headers={["Player", "Bonus", "BPS/90", "Per start"]}
          rows={insights.bonus.map((player) => ({
            id: player.id,
            cells: [
              <PlayerCell key="n" player={player} ownedIds={ownedIds} />,
              String(player.bonus),
              player.bps90.toFixed(1),
              player.bonus_per_start.toFixed(2),
            ],
          }))}
        />
      </section>
      {position == null ? (
        <section>
          <p className="kicker mb-3">Set pieces</p>
          <p className="caption mb-3">Penalty, corner and direct free-kick order.</p>
          <StatTable
            headers={["Club", "Penalties", "Corners", "Free kicks"]}
            rows={insights.set_pieces.map((club) => ({
              id: club.team_id,
              cells: [
                club.team_short,
                <TakerList key="p" takers={club.penalties} ownedIds={ownedIds} />,
                <TakerList key="c" takers={club.corners} ownedIds={ownedIds} />,
                <TakerList key="f" takers={club.freekicks} ownedIds={ownedIds} />,
              ],
            }))}
          />
        </section>
      ) : null}
    </div>
  );
}

function PositionFilter({ position }: { position: PositionId | undefined }) {
  return (
    <nav aria-label="Position" className="flex flex-wrap gap-x-5 gap-y-2">
      <FilterLink href="/dashboard/insights" active={position == null} label="All" />
      {POSITIONS.map((item) => (
        <FilterLink
          key={item.id}
          href={`/dashboard/insights?pos=${item.id}`}
          active={position === item.id}
          label={item.label}
        />
      ))}
    </nav>
  );
}

function FilterLink({ href, active, label }: { href: string; active: boolean; label: string }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`no-underline text-sm font-semibold ${active ? "text-ink" : "text-ink-faint"}`}
    >
      {label}
    </Link>
  );
}

function TakerList({ takers, ownedIds }: { takers: SetPiecePlayer[]; ownedIds: number[] }) {
  if (takers.length === 0) return <>—</>;
  return (
    <>
      {takers.map((taker, index) => (
        <span key={taker.id}>
          {index > 0 ? ", " : null}
          {taker.web_name}
          {ownedIds.includes(taker.id) ? <span className="caption ml-1">you own</span> : null}
        </span>
      ))}
    </>
  );
}
