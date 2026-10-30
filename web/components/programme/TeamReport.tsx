import { POSITIONS } from "@/components/dashboard/stats/format";
import { ReturnCompare } from "@/components/dashboard/stats/ReturnCompare";
import { StatTable } from "@/components/dashboard/stats/StatTable";
import { PitchSwitcher, type PitchLineup } from "@/components/programme/PitchSwitcher";
import type { PlayerRow, PublicTeam } from "@/lib/api";

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

const SCORE_FALLBACK = "Projected points this gameweek, starting XI plus captain.";

export function SquadScore({ value, reason }: { value: number; reason?: string }) {
  const explanation = reason?.trim() || SCORE_FALLBACK;
  return (
    <div className="mt-8 pb-8 border-b border-rule">
      <p className="kicker">Squad score</p>
      <p className="stat-xl mt-2 flex items-baseline gap-2">
        <span>{scoreLabel(value)}</span>
        <span className="caption">/10</span>
      </p>
      <p className="caption mt-3 max-w-xl">{explanation}</p>
    </div>
  );
}

export function TeamView({
  team,
  leaders,
  showHeader = true,
  lineup = "locked",
  showStats = true,
}: {
  team: PublicTeam;
  leaders?: Record<number, PlayerRow[]>;
  showHeader?: boolean;
  lineup?: PitchLineup;
  showStats?: boolean;
}) {
  return (
    <>
      {showHeader ? (
        <ReportHeader name={team.name} manager={team.manager} overallRank={team.overall_rank} />
      ) : null}
      <SquadScore value={team.squad_score} reason={team.squad_score_reason} />
      <div className="mt-8">
        <PitchSwitcher team={team} lineup={lineup} />
      </div>
      {showStats ? <TeamStats team={team} leaders={leaders} /> : null}
    </>
  );
}

function TeamStats({ team, leaders }: { team: PublicTeam; leaders?: Record<number, PlayerRow[]> }) {
  return (
    <>
      <div className="grid md:grid-cols-2 gap-x-12 gap-y-10 mt-10">
        <section>
          <p className="kicker mb-3">Due a return</p>
          <p className="caption mb-3">
            Fewer goals and assists than their chances were worth. The points often catch up, so these are usually holds.
          </p>
          <ReturnCompare
            players={team.underperforming}
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
            players={team.overperforming}
            direction="ahead"
            empty="Nobody in the squad is clearly ahead of their chances."
          />
        </section>
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-x-12 gap-y-10 mt-10">
        {POSITIONS.map((position) => (
          <section key={position.id}>
            <p className="kicker mb-3">{position.label}</p>
            <p className="caption mb-3">Top five by expected points.</p>
            <StatTable
              headers={["Player", "Proj"]}
              rows={(leaders?.[position.id] ?? []).map((player) => ({
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
