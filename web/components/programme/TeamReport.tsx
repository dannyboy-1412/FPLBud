import { PlayerCell, StatTable } from "@/components/dashboard/stats/StatTable";
import { PitchSwitcher, type PitchLineup } from "@/components/programme/PitchSwitcher";
import type { PlayerRow, PublicTeam, VarianceRow } from "@/lib/api";

const CLEAR_RETURN_GAP = 0.5;

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

function notableReturns(players: VarianceRow[] | undefined, direction: "short" | "ahead") {
  return (players ?? []).filter((player) =>
    direction === "short" ? player.xgi_delta >= CLEAR_RETURN_GAP : player.xgi_delta <= -CLEAR_RETURN_GAP,
  );
}

function returnsPhrase(goals: number, assists: number) {
  if (goals + assists === 0) return "No goals or assists yet";
  const parts: string[] = [];
  if (goals === 1) parts.push("1 goal");
  else if (goals > 1) parts.push(`${goals} goals`);
  if (assists === 1) parts.push("1 assist");
  else if (assists > 1) parts.push(`${assists} assists`);
  return parts.join(", ");
}

function ShareBar({ value, max }: { value: number; max: number }) {
  const width = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <span className="block h-1.5 bg-paper-deep" aria-hidden>
      <span className="block h-full bg-ink" style={{ width: `${width}%` }} />
    </span>
  );
}

function ReturnCompare({
  players,
  direction,
  empty,
}: {
  players: VarianceRow[] | undefined;
  direction: "short" | "ahead";
  empty: string;
}) {
  const rows = notableReturns(players, direction);
  if (rows.length === 0) {
    return <p className="caption">{empty}</p>;
  }
  return (
    <ul className="border-t border-ink">
      {rows.map((player) => {
        const actual = player.goals + player.assists;
        const scale = Math.max(player.xgi, actual, 0.1);
        const gap = Math.abs(player.xgi_delta).toFixed(1);
        return (
          <li key={player.id} className="py-3 border-b border-rule">
            <div className="flex items-baseline justify-between gap-4">
              <span className="min-w-0">
                <PlayerCell player={player} />
              </span>
              <span className="shrink-0 text-sm font-semibold nums">
                {direction === "short" ? `Short by ${gap}` : `Ahead by ${gap}`}
              </span>
            </div>
            <div className="mt-2 space-y-1.5">
              <div className="grid grid-cols-[6.25rem_1fr_2.25rem] items-center gap-x-3 text-sm">
                <span className="text-ink-soft">Should have</span>
                <ShareBar value={player.xgi} max={scale} />
                <span className="nums text-right">{player.xgi.toFixed(1)}</span>
              </div>
              <div className="grid grid-cols-[6.25rem_1fr_2.25rem] items-center gap-x-3 text-sm">
                <span className="text-ink-soft">Has</span>
                <ShareBar value={actual} max={scale} />
                <span className="nums text-right">{actual}</span>
              </div>
            </div>
            <p className="caption mt-1.5">{returnsPhrase(player.goals, player.assists)}</p>
          </li>
        );
      })}
    </ul>
  );
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
