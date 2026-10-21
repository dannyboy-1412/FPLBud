import { PlayerCell, StatTable } from "@/components/dashboard/stats/StatTable";
import { signed } from "@/components/dashboard/stats/format";
import { PitchSwitcher, type PitchLineup } from "@/components/programme/PitchSwitcher";
import type { PlayerRow, PublicTeam, VarianceRow } from "@/lib/api";

const POSITIONS = [
  { id: 1, label: "Goalkeeper" },
  { id: 2, label: "Defender" },
  { id: 3, label: "Midfielder" },
  { id: 4, label: "Striker" },
] as const;

function scoreLabel(value: number | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(1);
}

export function ReportHeader({
  name,
  manager,
  overallRank,
}: {
  name: string;
  manager: string;
  overallRank?: number | null;
}) {
  return (
    <>
      <p className="kicker">Team report</p>
      <h1 className="mt-1">{name}</h1>
      <p className="caption">{manager}</p>
      {overallRank ? <p className="caption">Overall rank {overallRank.toLocaleString("en-GB")}</p> : null}
    </>
  );
}

export function SquadScore({ value, caption }: { value: number; caption: string }) {
  return (
    <div className="mt-8 pb-8 border-b border-rule">
      <p className="kicker">Squad score</p>
      <p className="stat-xl mt-2 flex items-baseline gap-2">
        <span>{scoreLabel(value)}</span>
        <span className="caption">/10</span>
      </p>
      <p className="caption mt-2">{caption}</p>
    </div>
  );
}

function varianceRows(players: VarianceRow[] | undefined) {
  return (players ?? []).map((player) => ({
    id: player.id,
    cells: [
      <PlayerCell key="n" player={player} />,
      player.xgi.toFixed(1),
      player.goals + player.assists,
      signed(player.xgi_delta),
    ],
  }));
}

export function TeamView({
  team,
  leaders,
  showHeader = true,
  lineup = "locked",
}: {
  team: PublicTeam;
  leaders: Record<number, PlayerRow[]>;
  showHeader?: boolean;
  lineup?: PitchLineup;
}) {
  return (
    <>
      {showHeader ? (
        <ReportHeader name={team.name} manager={team.manager} overallRank={team.overall_rank} />
      ) : null}
      <SquadScore
        value={team.squad_score}
        caption="Projected points this gameweek, starting XI plus captain."
      />
      <div className="mt-8">
        <PitchSwitcher team={team} lineup={lineup} />
      </div>
      <div className="grid md:grid-cols-2 gap-x-12 gap-y-10 mt-10">
        <section>
          <p className="kicker mb-3">Underperforming</p>
          <p className="caption mb-3">xGI ahead of actual goal involvements.</p>
          <StatTable headers={["Player", "xGI", "G+A", "Δ"]} rows={varianceRows(team.underperforming)} />
        </section>
        <section>
          <p className="kicker mb-3">Overperforming</p>
          <p className="caption mb-3">Involvements ahead of xGI.</p>
          <StatTable headers={["Player", "xGI", "G+A", "Δ"]} rows={varianceRows(team.overperforming)} />
        </section>
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-x-12 gap-y-10 mt-10">
        {POSITIONS.map((position) => (
          <section key={position.id}>
            <p className="kicker mb-3">{position.label}</p>
            <p className="caption mb-3">Top five by expected points.</p>
            <StatTable
              headers={["Player", "Proj"]}
              rows={(leaders[position.id] ?? []).map((player) => ({
                id: player.id,
                cells: [
                  <>
                    {player.web_name} <span className="caption">{player.team_short}</span>
                  </>,
                  player.proj.toFixed(1),
                ],
              }))}
            />
          </section>
        ))}
      </div>
    </>
  );
}
