import type { FixtureChip, PublicTeam } from "@/lib/api";

type SquadPlayer = PublicTeam["squad_players"][number];

const KITS: Record<string, { fill: string; stroke: string }> = {
  ARS: { fill: "#EF0107", stroke: "#FFFFFF" },
  AVL: { fill: "#670E36", stroke: "#95BFE5" },
  BOU: { fill: "#B50E12", stroke: "#000000" },
  BRE: { fill: "#E30613", stroke: "#FFFFFF" },
  BHA: { fill: "#0057B8", stroke: "#FFFFFF" },
  BUR: { fill: "#6C1D45", stroke: "#99D6EA" },
  CHE: { fill: "#034694", stroke: "#FFFFFF" },
  CRY: { fill: "#1B458F", stroke: "#C4122E" },
  EVE: { fill: "#003399", stroke: "#FFFFFF" },
  FUL: { fill: "#FFFFFF", stroke: "#000000" },
  HUL: { fill: "#F5A12D", stroke: "#000000" },
  IPS: { fill: "#0044AA", stroke: "#FFFFFF" },
  LEE: { fill: "#FFCD00", stroke: "#1D428A" },
  LIV: { fill: "#C8102E", stroke: "#FFFFFF" },
  MCI: { fill: "#6CABDD", stroke: "#1C2C5B" },
  MUN: { fill: "#DA291C", stroke: "#FFFFFF" },
  NEW: { fill: "#241F20", stroke: "#FFFFFF" },
  NFO: { fill: "#DD0000", stroke: "#FFFFFF" },
  SUN: { fill: "#EB172B", stroke: "#FFFFFF" },
  TOT: { fill: "#FFFFFF", stroke: "#132257" },
  WHU: { fill: "#7A263A", stroke: "#1BB1E7" },
  WOL: { fill: "#FDB913", stroke: "#231F20" },
};

const PLAIN_KIT = { fill: "#F4FFF8", stroke: "#0C3B24" };

function kitFor(club: string | undefined) {
  if (!club) return PLAIN_KIT;
  return KITS[club.toUpperCase()] ?? PLAIN_KIT;
}

export function Shirt({ club }: { club?: string }) {
  const kit = kitFor(club);
  return (
    <svg className="pitch-shirt" width="36" height="32" viewBox="0 0 36 32" aria-hidden>
      <path
        d="M10 5.5 14.2 2.2h7.6L26 5.5 33.2 8.4 29.4 13.2 26 11.4V28H10V11.4L6.6 13.2 2.8 8.4Z"
        fill={kit.fill}
        stroke={kit.stroke}
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M14.2 2.6c1.2 2.6 2.4 3.8 3.8 3.8s2.6-1.2 3.8-3.8" fill="none" stroke={kit.stroke} strokeWidth="1.2" />
    </svg>
  );
}

function fixtureBars(fixtures: FixtureChip[] | undefined) {
  if (!fixtures?.length) {
    return [{ key: "blank", label: "—" }];
  }
  return fixtures.map((fixture, index) => ({
    key: `${fixture.opponent}-${fixture.is_home ? "H" : "A"}-${index}`,
    label: `${fixture.opponent} (${fixture.is_home ? "H" : "A"})`,
  }));
}

function fixtureSummary(fixtures: FixtureChip[] | undefined) {
  if (!fixtures?.length) return "no fixture";
  return fixtures.map((fixture) => `${fixture.opponent} ${fixture.is_home ? "home" : "away"}`).join(", ");
}

type PlayingChance = "fit" | "doubt" | "out";

function playingChance(player: SquadPlayer): PlayingChance {
  const chance = player.chance_of_playing_next_round;
  if (chance != null && chance < 100) return chance >= 75 ? "doubt" : "out";
  if (chance == null && player.status === "d") return "doubt";
  if (chance == null && player.status && player.status !== "a") return "out";
  return "fit";
}

function chanceLabel(player: SquadPlayer, chance: PlayingChance) {
  if (chance === "fit") return null;
  const percent = player.chance_of_playing_next_round;
  if (percent != null) return `${percent}% chance of playing`;
  return chance === "doubt" ? "doubtful" : "unlikely to play";
}

function PlayerCard({
  player,
  incoming,
  order,
}: {
  player: SquadPlayer;
  incoming?: boolean;
  order?: number;
}) {
  const club = player.team_short?.toUpperCase() ?? "";
  const bars = fixtureBars(player.fixtures);
  const chance = playingChance(player);
  const chanceText = chanceLabel(player, chance);
  const role = player.is_captain ? "captain" : player.is_vice_captain ? "vice-captain" : null;
  return (
    <button
      type="button"
      className={`pitch-card${incoming ? " is-in" : ""}`}
      aria-label={`${player.web_name}, ${club || "club unknown"}, ${fixtureSummary(player.fixtures)}${chanceText ? `, ${chanceText}` : ""}${role ? `, ${role}` : ""}`}
    >
      {order != null ? <span className="pitch-order">{order}</span> : null}
      {player.is_captain ? <span className="pitch-badge is-c">C</span> : null}
      {!player.is_captain && player.is_vice_captain ? <span className="pitch-badge is-v">V</span> : null}
      <Shirt club={club} />
      <span className="pitch-plate">
        <span className={`pitch-name${chance === "fit" ? "" : ` is-${chance}`}`} title={chanceText ?? player.web_name}>
          {player.web_name}
        </span>
        <span className="pitch-club">{club || "—"}</span>
        {bars.map((bar) => (
          <span key={bar.key} className="pitch-opp">
            {bar.label}
          </span>
        ))}
      </span>
    </button>
  );
}

export function PitchMarkings() {
  return (
    <div className="pitch-mark" aria-hidden>
      <span className="half" />
      <span className="circle" />
      <span className="spot" />
      <span className="box far" />
      <span className="six far" />
      <span className="box near" />
      <span className="six near" />
      <span className="arc far" />
      <span className="arc near" />
    </div>
  );
}

export function Pitch({
  team,
  incomingIds = [],
}: {
  team: PublicTeam;
  incomingIds?: number[];
}) {
  const byPos: Record<number, SquadPlayer[]> = { 1: [], 2: [], 3: [], 4: [] };
  const starters = team.squad_players.filter((player) => player.squad_position <= 11);
  const bench = team.squad_players
    .filter((player) => player.squad_position > 11)
    .sort((a, b) => a.squad_position - b.squad_position);
  for (const player of starters) {
    byPos[player.position_id]?.push(player);
  }
  for (const position of [1, 2, 3, 4]) {
    byPos[position]?.sort((a, b) => a.squad_position - b.squad_position);
  }

  return (
    <div className="pitch-unit">
      <div className="pitch" aria-label="Formation">
        <PitchMarkings />
        <div className="pitch-rows">
          {[1, 2, 3, 4].map((position) => (
            <div key={position} className="pitch-row">
              {(byPos[position] ?? []).map((player) => (
                <PlayerCard
                  key={player.element}
                  player={player}
                  incoming={incomingIds.includes(player.element)}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="pitch-subs">
        <p className="kicker">Substitutes</p>
        <div className="pitch-row">
          {bench.map((player, index) => (
            <PlayerCard
              key={player.element}
              player={player}
              order={index + 1}
              incoming={incomingIds.includes(player.element)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
