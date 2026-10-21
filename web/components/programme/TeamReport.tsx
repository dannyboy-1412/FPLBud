import { GoogleButton } from "@/components/programme/GoogleButton";
import { ReportPlans } from "@/components/programme/TryEdition";
import { PlayerCell, StatTable } from "@/components/dashboard/stats/StatTable";
import { signed } from "@/components/dashboard/stats/format";
import type { PublicTeam, TeamReport } from "@/lib/api";

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
      {overallRank ? <p className="caption">Overall rank {overallRank.toLocaleString()}</p> : null}
    </>
  );
}

export function SquadScore({ value, caption }: { value: number; caption: string }) {
  return (
    <div className="mt-8 pb-8 border-b border-rule">
      <p className="kicker">Squad score</p>
      <p className="stat-xl mt-2">{scoreLabel(value)}</p>
      <p className="caption mt-2">{caption}</p>
    </div>
  );
}

export function GuestReport({ team }: { team: PublicTeam }) {
  return (
    <>
      <ReportHeader name={team.name} manager={team.manager} overallRank={team.overall_rank} />
      <SquadScore value={team.squad_score} caption="Starting XI, next gameweek. Sign in for the rest." />
      <LockedSections entryId={team.entry_id} />
    </>
  );
}

function LockedSections({ entryId }: { entryId: number }) {
  const blocks = [
    ["Expected points", "Next gameweek projection for your starting XI."],
    ["Transfer suggestions", "Who to sell, who to buy, and whether a hit is worth it."],
    ["Performing players", "The squad players putting up the most recent points."],
    ["Underperforming players", "Squad players whose xGI is ahead of actual returns."],
  ] as const;
  return (
    <div className="mt-10">
      <div className="grid md:grid-cols-2 gap-x-12 gap-y-8">
        {blocks.map(([title, copy]) => (
          <section key={title} className="border-b border-rule pb-6">
            <p className="kicker">{title}</p>
            <p className="prose-body mt-3 text-ink-faint">{copy}</p>
          </section>
        ))}
      </div>
      <div className="mt-8 max-w-xs">
        <GoogleButton entryId={entryId} label="Sign in to unlock your report" />
      </div>
    </div>
  );
}

export function MemberSections({ report }: { report: TeamReport }) {
  return (
    <div className="space-y-12 mt-10">
      <section>
        <p className="kicker">Expected points</p>
        <p className="stat-xl mt-2">{report.expected_points.total.toFixed(1)}</p>
        <p className="caption mt-2">Next gameweek, starting XI.</p>
        <div className="mt-4">
          <StatTable
            headers={["Player", "Proj"]}
            rows={report.expected_points.players.map((p) => ({
              id: p.id,
              cells: [p.web_name, p.proj.toFixed(1)],
            }))}
          />
        </div>
      </section>
      <section>
        <p className="kicker mb-3">Transfer suggestions</p>
        {Object.keys(report.plans).length === 0 ? (
          <p className="caption">Plans aren&apos;t ready yet.</p>
        ) : (
          <ReportPlans plans={report.plans} />
        )}
      </section>
      <div className="grid md:grid-cols-2 gap-x-12 gap-y-10">
        <section>
          <p className="kicker mb-3">Performing</p>
          <p className="caption mb-3">Squad players by recent points.</p>
          <StatTable
            headers={["Player", "Last 6", "Form"]}
            rows={report.performing.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} />,
                p.recent_points,
                p.form.toFixed(1),
              ],
            }))}
          />
        </section>
        <section>
          <p className="kicker mb-3">Underperforming</p>
          <p className="caption mb-3">xGI ahead of actual goal involvements.</p>
          <StatTable
            headers={["Player", "xGI", "G+A", "Δ"]}
            rows={report.underperforming.map((p) => ({
              id: p.id,
              cells: [
                <PlayerCell key="n" player={p} />,
                p.xgi.toFixed(1),
                p.goals + p.assists,
                signed(p.xgi_delta),
              ],
            }))}
          />
        </section>
      </div>
    </div>
  );
}
