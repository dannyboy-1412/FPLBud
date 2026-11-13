import type { PublicTeam } from "@/lib/api";
import {
  SAMPLE_CAPTION,
  SAMPLE_IN_ELEMENT,
  SAMPLE_LINES,
  SAMPLE_OUT,
  SAMPLE_SUMMARY,
  SAMPLE_XI,
} from "@/components/programme/landing-sample";
import { PitchMarkings, Shirt } from "@/components/programme/Pitch";

type SamplePlayer = PublicTeam["squad_players"][number];

function fixtureLabel(player: SamplePlayer) {
  const fixture = player.fixtures?.[0];
  if (!fixture) return "—";
  return `${fixture.opponent} (${fixture.is_home ? "H" : "A"})`;
}

function SampleCard({ player, motion }: { player: SamplePlayer; motion?: "in" | "out" }) {
  const club = player.team_short?.toUpperCase() ?? "";
  const motionClass = motion === "in" ? " landing-in" : motion === "out" ? " landing-out" : "";
  return (
    <div className={`landing-player${motionClass}`}>
      {player.is_captain ? <span className="pitch-badge is-c landing-band">C</span> : null}
      {!player.is_captain && player.is_vice_captain ? <span className="pitch-badge is-v">V</span> : null}
      <Shirt club={club} />
      <span className="pitch-plate">
        <span className="pitch-name">{player.web_name}</span>
        <span className="pitch-club">{club || "—"}</span>
        <span className="pitch-opp">{fixtureLabel(player)}</span>
      </span>
    </div>
  );
}

function Slot({ player }: { player: SamplePlayer }) {
  if (player.element !== SAMPLE_IN_ELEMENT) return <SampleCard player={player} />;
  return (
    <div className="landing-swap">
      <SampleCard player={player} motion="in" />
      <SampleCard player={SAMPLE_OUT} motion="out" />
    </div>
  );
}

export function LandingPitch() {
  const rows = [1, 2, 3, 4].map((position) =>
    SAMPLE_XI.filter((player) => player.position_id === position).sort(
      (a, b) => a.squad_position - b.squad_position,
    ),
  );

  return (
    <figure className="landing-pitch" role="img" aria-label={SAMPLE_SUMMARY}>
      <div className="pitch-unit">
        <div className="pitch">
          <PitchMarkings />
          <div className="pitch-rows landing-rows">
            {rows.map((row) => (
              <div key={row[0]?.position_id} className="pitch-row">
                {row.map((player) => (
                  <Slot key={player.element} player={player} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
      <figcaption className="landing-caption">{SAMPLE_CAPTION}</figcaption>
      <dl className="landing-slip">
        {SAMPLE_LINES.map(([term, detail]) => (
          <div key={term}>
            <dt>{term}</dt>
            <dd>{detail}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}
