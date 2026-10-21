import { IntentPrefetchLink } from "@/components/dashboard/IntentPrefetchLink";
import { getInsights, getMe, getOwnedIds } from "@/lib/server/data";
import { POS, signed } from "./format";
import { PlayerCell, StatTable } from "./StatTable";

function taker(list: { web_name: string; order: number }[]) {
  if (list.length === 0) return "—";
  return list.map((p) => (p.order === 1 ? p.web_name : `${p.web_name} (${p.order})`)).join(" / ");
}

export async function InsightsSection({ position }: { position?: number }) {
  const ownedIdsPromise = getOwnedIds();
  const me = await getMe();
  const data = await getInsights(position, me.profile.weights);
  const ownedIds = (await ownedIdsPromise) ?? [];
  const filters = [
    { pos: undefined, label: "All" },
    { pos: 1, label: "GKP" },
    { pos: 2, label: "DEF" },
    { pos: 3, label: "MID" },
    { pos: 4, label: "FWD" },
  ] as const;
  return (
    <div className="space-y-10">
      <div className="flex flex-wrap gap-3">
        {filters.map((f) => {
          const href = f.pos ? `/dashboard/insights?pos=${f.pos}` : "/dashboard/insights";
          const active = (position ?? undefined) === f.pos;
          return (
            <IntentPrefetchLink
              key={f.label}
              href={href}
              prefetchOnIntent="full"
              className={`btn ${active ? "btn-primary" : "btn-secondary"}`}
              aria-current={active ? "page" : undefined}
            >
              {f.label}
            </IntentPrefetchLink>
          );
        })}
      </div>
      <div className="grid md:grid-cols-2 gap-x-12 gap-y-10">
        <section>
          <p className="kicker mb-3">In form</p>
          <StatTable
            headers={["Player", "Last 6", "Form", "xGI/90"]}
            rows={data.in_form.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
                p.recent_points,
                p.form.toFixed(1),
                p.xgi90.toFixed(2),
              ],
            }))}
          />
        </section>
        <section>
          <p className="kicker mb-3">Differentials</p>
          <p className="caption mb-3">Under 10% owned, next 3 GWs.</p>
          <StatTable
            headers={["Player", "Own%", "Proj"]}
            rows={data.differentials.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
                `${p.selected_by_percent.toFixed(1)}%`,
                p.proj.toFixed(1),
              ],
            }))}
          />
        </section>
        <section>
          <p className="kicker mb-3">Due a return</p>
          <p className="caption mb-3">xGI ahead of actual goal involvements.</p>
          <StatTable
            headers={["Player", "xGI", "G+A", "Δ"]}
            rows={data.underperformers.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
                p.xgi.toFixed(1),
                p.goals + p.assists,
                signed(p.xgi_delta),
              ],
            }))}
          />
        </section>
        <section>
          <p className="kicker mb-3">Overperforming</p>
          <p className="caption mb-3">Regression risks: involvements ahead of xGI.</p>
          <StatTable
            headers={["Player", "xGI", "G+A", "Δ"]}
            rows={data.overperformers.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
                p.xgi.toFixed(1),
                p.goals + p.assists,
                signed(p.xgi_delta),
              ],
            }))}
          />
        </section>
        <section>
          <p className="kicker mb-3">Defensive contributions</p>
          <p className="caption mb-3">Hit rate is the share of starts that cleared the 2-pt threshold.</p>
          <StatTable
            headers={["Player", "DC/90", "Hit rate", "Thr"]}
            rows={data.defensive.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
                p.dc_per_90.toFixed(1),
                `${Math.round(p.hit_rate * 100)}%`,
                p.threshold,
              ],
            }))}
          />
        </section>
        <section>
          <p className="kicker mb-3">Bonus magnets</p>
          <StatTable
            headers={["Player", "Bonus", "BPS/90", "/start"]}
            rows={data.bonus.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
                p.bonus,
                p.bps90.toFixed(1),
                p.bonus_per_start.toFixed(2),
              ],
            }))}
          />
        </section>
      </div>
      {data.set_pieces.length > 0 ? (
        <section>
          <p className="kicker mb-3">Set-piece takers</p>
          <StatTable
            headers={["Team", "Penalties", "Corners", "Free kicks"]}
            rows={data.set_pieces.map((team) => ({
              id: team.team_id,
              cells: [team.team_short, taker(team.penalties), taker(team.corners), taker(team.freekicks)],
            }))}
          />
        </section>
      ) : position ? (
        <p className="caption">Set-piece lists show for All positions.</p>
      ) : null}
      <p className="caption">
        Form tables skip players with fewer than 180 minutes. Position filter: {position ? POS[position] : "all"}.
      </p>
    </div>
  );
}
