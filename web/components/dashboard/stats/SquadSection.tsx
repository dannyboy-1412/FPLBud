import { loadAccount, renderApi } from "@/lib/server/render-api";
import { getMySquadStats, getOwnedIds } from "@/lib/server/data";
import { PlayerCell, StatTable } from "./StatTable";

function fixtureLabel(fixtures: { opponent: string; fdr: number; is_home: boolean }[]) {
  if (fixtures.length === 0) return "Blank";
  return fixtures.map((f) => `${f.is_home ? "H" : "A"} ${f.opponent} (${f.fdr})`).join(" · ");
}

export async function SquadSection() {
  const account = await loadAccount();
  if (!account.ok) return null;
  return renderApi(() => loadSquad());
}

async function loadSquad() {
  const ownedIdsPromise = getOwnedIds();
  const data = await getMySquadStats();
  const ownedIds = await ownedIdsPromise;
  const { board, gap, crowd } = data.captaincy;
  return (
    <div className="space-y-10">
      <section>
        <p className="kicker mb-2">Captaincy board</p>
        {crowd ? (
          <p className="caption mb-3">
            Last GW the crowd captained {crowd.web_name} ({crowd.team_short}) for {crowd.event_points} pts.
          </p>
        ) : null}
        {board.length >= 2 ? (
          <p className="caption mb-3">
            {board[0].web_name} leads {board[1].web_name} by {gap.toFixed(1)} projected points.
          </p>
        ) : null}
        <StatTable
          headers={["Player", "Proj", "Own%", "Fixture", "Avail"]}
          rows={board.map((p) => ({
            id: p.id,
            cells: [
              <>
                <PlayerCell player={p} ownedIds={ownedIds} />
                {p.is_captain ? <span className="caption ml-1">C</span> : null}
                {p.is_vice_captain ? <span className="caption ml-1">VC</span> : null}
              </>,
              p.proj.toFixed(1),
              `${p.selected_by_percent.toFixed(1)}%`,
              fixtureLabel(p.fixtures),
              p.chance_of_playing_next_round == null ? p.status : `${p.chance_of_playing_next_round}%`,
            ],
          }))}
        />
      </section>
      <div className="grid md:grid-cols-3 gap-6">
        <div className="border-b border-rule pb-3">
          <p className="kicker">XI ownership</p>
          <p className="stat mt-2">{data.ownership.xi_avg_ownership.toFixed(1)}%</p>
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Template in squad</p>
          <p className="stat mt-2">
            {data.ownership.template_count}
            <span className="caption ml-2">of {data.ownership.squad_size}</span>
          </p>
        </div>
        <div className="border-b border-rule pb-3">
          <p className="kicker">Differentials</p>
          <p className="stat mt-2">{data.ownership.differential_count}</p>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-x-12 gap-y-10">
        <section>
          <p className="kicker mb-3">Template threats</p>
          <p className="caption mb-3">High-owned players you don&apos;t have, ranked by ownership × projection.</p>
          <StatTable
            headers={["Player", "Own%", "Proj", "Threat"]}
            rows={data.template_threats.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
                `${p.selected_by_percent.toFixed(1)}%`,
                p.proj.toFixed(1),
                p.threat.toFixed(0),
              ],
            }))}
          />
        </section>
        <section>
          <p className="kicker mb-3">Your differentials</p>
          <p className="caption mb-3">Squad players under 10% owned.</p>
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
      </div>
    </div>
  );
}
