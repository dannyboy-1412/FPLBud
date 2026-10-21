import { Pitch } from "@/components/programme/Pitch";
import { TeamSheet } from "@/components/programme/TeamSheet";
import { getPublicTeam } from "@/lib/server/data";

export default async function PitchPreviewPage() {
  const team = await getPublicTeam(7426026);
  return (
    <div className="matchday">
      <p className="kicker">Gameweek preview</p>
      <h1 className="mt-1">{team.name}</h1>
      <div className="broadsheet mt-6">
        <Pitch team={team} />
        <div className="col-rule" />
        <TeamSheet team={team} />
      </div>
    </div>
  );
}
