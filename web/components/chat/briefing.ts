const LONDON = "Europe/London";

const CHIP_LABELS: Record<string, string> = {
  wildcard: "Wildcard",
  wc: "Wildcard",
  freehit: "Free Hit",
  free_hit: "Free Hit",
  bboost: "Bench Boost",
  bench_boost: "Bench Boost",
  "3xc": "Triple Captain",
  triple_captain: "Triple Captain",
};

export type BriefingEvent = { id: number; name: string; deadline_time: string } | null;

export type BriefingPlayer = {
  web_name: string;
  status: string;
  chance_of_playing_next_round: number | null;
  is_captain: boolean;
  is_vice_captain: boolean;
};

export type BriefingSquad = {
  manager: string;
  bank: number;
  free_transfers: number;
  chips_available: Array<{ name: string }>;
  squad_players: BriefingPlayer[];
};

export type PromptIcon = "captain" | "fitness" | "transfer" | "chip" | "fixtures";

export type SquadPrompt = { icon: PromptIcon; question: string };

export const GENERIC_PROMPTS: SquadPrompt[] = [
  { icon: "captain", question: "Who should I captain?" },
  { icon: "transfer", question: "Is a hit worth it?" },
  { icon: "chip", question: "Should I use a chip this week?" },
  { icon: "fixtures", question: "Which of my players have the best fixtures?" },
];

export function greetingName(team: Pick<BriefingSquad, "manager"> | null, event: BriefingEvent, now: Date): string {
  const first = firstName(team?.manager ?? "");
  if (!first) return event ? `Ready for Gameweek ${event.id}?` : "The desk is open";
  return `${partOfDay(now)}, ${first}`;
}

export function statusLine(team: BriefingSquad | null, event: BriefingEvent, now: Date): string {
  const parts: string[] = [];
  if (event) {
    parts.push(`GW${event.id} deadline ${deadlineStamp(event.deadline_time)}`);
    const left = timeLeft(event.deadline_time, now);
    if (left) parts.push(left);
  }
  if (team) {
    parts.push(team.free_transfers === 1 ? "1 free transfer" : `${team.free_transfers} free transfers`);
    parts.push(money(team.bank));
    const flagged = team.squad_players.filter(isFlagged).length;
    if (flagged === 1) parts.push("1 flagged");
    else if (flagged > 1) parts.push(`${flagged} flagged`);
  }
  return parts.join(" · ");
}

export function squadPrompts(team: BriefingSquad | null): SquadPrompt[] {
  if (!team) return GENERIC_PROMPTS;
  const captain = team.squad_players.find((player) => player.is_captain);
  const vice = team.squad_players.find((player) => player.is_vice_captain);
  const flagged = worstFlagged(team.squad_players);
  const chip = team.chips_available.find((item) => item.name.trim());
  return [
    captain && vice
      ? { icon: "captain", question: `Captain ${captain.web_name} or ${vice.web_name}?` }
      : GENERIC_PROMPTS[0],
    flagged
      ? { icon: "fitness", question: `Is ${flagged.web_name} likely to start?` }
      : GENERIC_PROMPTS[3],
    flagged && team.bank > 0
      ? { icon: "transfer", question: `Replace ${flagged.web_name} with ${money(team.bank)}?` }
      : GENERIC_PROMPTS[1],
    chip
      ? { icon: "chip", question: `Play my ${chipLabel(chip.name)} this week?` }
      : GENERIC_PROMPTS[2],
  ];
}

export function chipLabel(name: string): string {
  const key = name.trim().toLowerCase();
  const known = CHIP_LABELS[key];
  if (known) return known;
  if (!key) return name;
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function firstName(manager: string): string {
  return manager.trim().split(/\s+/)[0] ?? "";
}

function partOfDay(now: Date): string {
  const hour = londonHour(now);
  if (hour >= 5 && hour < 12) return "Morning";
  if (hour >= 12 && hour < 17) return "Afternoon";
  if (hour >= 17 && hour < 22) return "Evening";
  return "Hello";
}

function londonHour(now: Date): number {
  const value = new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON,
    hour: "2-digit",
    hourCycle: "h23",
  })
    .formatToParts(now)
    .find((part) => part.type === "hour")?.value;
  const hour = value ? Number(value) : now.getUTCHours();
  return hour === 24 ? 0 : hour;
}

function deadlineStamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  return `${value("weekday")} ${value("day")} ${value("month")}, ${value("hour")}:${value("minute")}`;
}

function timeLeft(iso: string, now: Date): string {
  const ms = new Date(iso).getTime() - now.getTime();
  if (Number.isNaN(ms)) return "";
  if (ms <= 0) return "deadline passed";
  const minutes = Math.floor(ms / 60_000);
  const days = Math.floor(minutes / (60 * 24));
  const hours = Math.floor((minutes % (60 * 24)) / 60);
  if (days > 0) return `${days}d ${hours}h left`;
  if (hours > 0) return `${hours}h ${minutes % 60}m left`;
  return `${minutes % 60}m left`;
}

function money(tenths: number): string {
  return `£${(tenths / 10).toFixed(1)}m`;
}

function isFlagged(player: BriefingPlayer): boolean {
  const chance = player.chance_of_playing_next_round;
  if (chance != null && chance < 100) return true;
  if (chance == null && player.status && player.status !== "a") return true;
  return false;
}

function worstFlagged(players: BriefingPlayer[]): BriefingPlayer | null {
  const flagged = players.filter(isFlagged);
  if (flagged.length === 0) return null;
  return flagged.reduce((worst, player) => (doubtScore(player) < doubtScore(worst) ? player : worst));
}

function doubtScore(player: BriefingPlayer): number {
  const chance = player.chance_of_playing_next_round;
  if (chance != null) return chance;
  return player.status === "d" ? 50 : 0;
}
