import type { FixtureChip, PublicTeam } from "@/lib/api";

type SamplePlayer = PublicTeam["squad_players"][number];

function player(
  element: number,
  webName: string,
  club: string,
  positionId: number,
  squadPosition: number,
  fixture: FixtureChip,
  role?: "c" | "v",
): SamplePlayer {
  return {
    element,
    web_name: webName,
    team_id: 0,
    team_short: club,
    position_id: positionId,
    now_cost: 0,
    status: "a",
    chance_of_playing_next_round: null,
    news: null,
    is_captain: role === "c",
    is_vice_captain: role === "v",
    squad_position: squadPosition,
    fixtures: [fixture],
  };
}

const ARS: FixtureChip = { opponent: "NEW", fdr: 3, is_home: false };
const LIV: FixtureChip = { opponent: "MUN", fdr: 3, is_home: true };
const MCI: FixtureChip = { opponent: "FUL", fdr: 2, is_home: true };
const CHE: FixtureChip = { opponent: "LEE", fdr: 3, is_home: true };

export const SAMPLE_IN_ELEMENT = 9011;

export const SAMPLE_OUT = player(9012, "Pickford", "EVE", 1, 1, {
  opponent: "BRE",
  fdr: 4,
  is_home: false,
});

export const SAMPLE_XI: SamplePlayer[] = [
  player(SAMPLE_IN_ELEMENT, "Raya", "ARS", 1, 1, ARS),
  player(9002, "Gabriel", "ARS", 2, 2, ARS),
  player(9003, "Jacquet", "LIV", 2, 3, LIV),
  player(9004, "Van de Ven", "TOT", 2, 4, { opponent: "IPS", fdr: 2, is_home: true }),
  player(9005, "Rúben", "MCI", 2, 5, MCI),
  player(9006, "Palmer", "CHE", 3, 6, CHE, "c"),
  player(9007, "Mbeumo", "MUN", 3, 7, { opponent: "LIV", fdr: 4, is_home: false }, "v"),
  player(9008, "Wirtz", "LIV", 3, 8, LIV),
  player(9009, "Rice", "ARS", 3, 9, ARS),
  player(9010, "Haaland", "MCI", 4, 10, MCI),
  player(9013, "Isak", "LIV", 4, 11, LIV),
];

export const SAMPLE_LINES = [
  ["Captain", "Palmer, projected 8.4 this week."],
  ["Transfer", "Pickford out, Raya in, worth 2.1 points over the next three."],
  ["Bench", "Kelleher, Konsa, Gakpo and Marmoush, in that order."],
] as const;

export const SAMPLE_CAPTION = "Example plan";

export const SAMPLE_SUMMARY =
  "Example plan. Palmer wears the captain armband, projected 8.4 this week. Pickford leaves and Raya arrives, worth 2.1 points over the next three. The bench is Kelleher, Konsa, Gakpo and Marmoush, in that order.";
