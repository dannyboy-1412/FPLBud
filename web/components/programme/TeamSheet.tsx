import type { PublicTeam } from "@/lib/api";

const CHIP_LABEL: Record<string, string> = {
  wildcard: "Wildcard",
  freehit: "Free Hit",
  bboost: "Bench Boost",
  "3xc": "Triple Captain",
};

function pounds(tenths: number) {
  return `£${(tenths / 10).toFixed(1)}m`;
}

export function TeamSheet({ team }: { team: PublicTeam }) {
  const used = new Set(team.chips_used.map((c) => c.name));
  return (
    <aside className="team-sheet">
      <p className="kicker mb-4">Team sheet</p>
      <div className="flex justify-between items-baseline py-3 border-b border-rule">
        <span className="kicker">Bank</span>
        <span className="stat">{pounds(team.bank)}†</span>
      </div>
      <div className="flex justify-between items-baseline py-3 border-b border-rule">
        <span className="kicker">Free transfers</span>
        <span className="stat">{team.free_transfers}†</span>
      </div>
      <div className="flex justify-between items-baseline py-3 border-b border-rule">
        <span className="kicker">Team value</span>
        <span className="stat">{pounds(team.team_value)}</span>
      </div>
      <div className="py-3 border-b border-rule">
        <span className="kicker">Chips</span>
        <div className="mt-2">
          {team.chips_available.map((c) => (
            <span key={c.name} className="block tracking-wide uppercase text-sm">
              {CHIP_LABEL[c.name] ?? c.name}{" "}
              <span className="caption">until GW{c.stop_event}</span>
            </span>
          ))}
          {team.chips_used.map((c) => (
            <span key={`${c.name}-${c.event}`} className="block text-ink-faint line-through tracking-wide uppercase text-sm">
              {CHIP_LABEL[c.name] ?? c.name}
            </span>
          ))}
          {used.size === 0 && team.chips_available.length === 0 ? <span className="caption">None listed</span> : null}
        </div>
      </div>
      <div className="py-3">
        <span className="kicker">Flags</span>
        <ul className="mt-2 list-none p-0">
          {team.flags.length === 0 ? <li className="caption">No availability concerns</li> : null}
          {team.flags.map((f) => (
            <li key={f.element} className="caption mb-1">
              {f.web_name ?? f.element}: {f.news || f.status}
            </li>
          ))}
        </ul>
      </div>
      <p className="caption mt-4">
        † Estimated. FPL doesn&apos;t publish selling prices or free transfers publicly. Edit if ours are wrong.
      </p>
      <p className="caption mt-2">{team.caveat}</p>
    </aside>
  );
}
