const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export class TeamNotFoundError extends Error {
  readonly code = "TEAM_NOT_FOUND" as const;
  constructor(public entryId: number) {
    super("team not found");
    this.name = "TeamNotFoundError";
  }
}

export function isTeamNotFound(err: unknown): boolean {
  if (err instanceof TeamNotFoundError) return true;
  if (err instanceof ApiError && err.status === 404) return true;
  return (
    typeof err === "object" &&
    err !== null &&
    "code" in err &&
    (err as { code: unknown }).code === "TEAM_NOT_FOUND"
  );
}

export async function api<T>(
  path: string,
  init: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (init.token) {
    headers.set("Authorization", `Bearer ${init.token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    if (response.status === 429) {
      throw new ApiError(429, "Easy, gaffer. Too many requests. Try again in a minute.");
    }
    throw new ApiError(response.status, typeof detail === "string" ? detail : "request failed");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export type Weights = {
  form: number;
  fixture: number;
  home: number;
  xgi: number;
  value: number;
  minutes: number;
  trend: number;
};

export type Flag = {
  element: number;
  web_name?: string;
  status: string;
  chance_of_playing_next_round: number | null;
  news: string;
};

export type ChipTip = {
  chip: string;
  recommend: string;
  expected_gain: number;
  reason_codes: string[];
  expires_soon?: boolean;
  stop_event?: number;
};

export type Transfer = {
  out: number;
  in: number;
  out_name: string;
  in_name: string;
  cost_delta: number;
  metric_deltas?: Record<string, number>;
};

export type HorizonPlan = {
  horizon: number;
  transfers: Transfer[];
  hits: number;
  gain_vs_roll: number;
  roll_alternative?: unknown;
  fewer_alternative?: unknown;
  xi: Array<Record<string, unknown>>;
  bench: Array<Record<string, unknown>>;
  captain: Record<string, unknown>;
  vice: Record<string, unknown>;
  chips: ChipTip[];
  flags: Flag[];
  reason_codes: string[];
  projected_points_by_gw: Record<string, number>;
  bank_after?: number;
  headline?: string;
  explanation?: string;
  explanation_source?: string;
};

export type PublicTeam = {
  entry_id: number;
  name: string;
  manager: string;
  overall_rank: number | null;
  event: number;
  picks: Array<Record<string, unknown>>;
  squad_players: Array<{
    element: number;
    web_name: string;
    team_id: number;
    team_short?: string;
    position_id: number;
    now_cost: number;
    status: string;
    chance_of_playing_next_round: number | null;
    news: string | null;
    is_captain: boolean;
    is_vice_captain: boolean;
    squad_position: number;
    fixtures?: FixtureChip[];
  }>;
  bank: number;
  team_value: number;
  free_transfers: number;
  selling_prices: Record<string, number>;
  chips_available: Array<{ name: string; stop_event: number }>;
  chips_used: Array<{ name: string; event: number }>;
  active_chip: string | null;
  flags: Flag[];
  estimated: boolean;
  caveat: string;
  squad_score: number;
  underperforming: VarianceRow[];
  overperforming: VarianceRow[];
};

export type Meta = {
  season_id: string | null;
  current_event: { id: number; name: string; deadline_time: string } | null;
  next_event: { id: number; name: string; deadline_time: string } | null;
  data_version: number | null;
  default_weights: Weights;
  metric_labels: Record<string, string>;
  metric_descriptions: Record<string, string>;
};

export type AgentRun = {
  id: number;
  status: string;
  stage: string | null;
  progress: number;
  error: string | null;
  trigger?: string;
  created_at: string;
  finished_at: string | null;
  data_version: number | null;
  results: Record<string, HorizonPlan> | null;
};

export type Profile = {
  display_name: string | null;
  avatar_url?: string | null;
  fpl_entry_id: number | null;
  fpl_team_name: string | null;
  weights: Weights;
  default_horizon: number;
  max_hits: number;
};

export type MeResponse = {
  profile: Profile;
  snapshot: unknown | null;
  latest_run_id: number | null;
};

export type PlayerRow = {
  id: number;
  web_name: string;
  team_short: string;
  position_id: number;
  now_cost: number;
  proj: number;
  rank: number;
  scores: Record<string, number>;
};

export type HorizonTab = "1" | "3" | "5";

export type StatPlayer = {
  id: number;
  web_name: string;
  team_short: string;
  position_id: number;
  now_cost: number;
  selected_by_percent: number;
};

export type TransferMover = StatPlayer & {
  transfers_in_event: number;
  transfers_out_event: number;
  net: number;
};

export type PriceMover = StatPlayer & {
  cost_change_event: number;
  cost_change_start: number;
  daily_change: number;
};

export type NetMover = StatPlayer & {
  net_24h: number;
  daily_change: number;
};

export type PressureRow = StatPlayer & {
  net: number;
  owners: number;
  pressure: number;
};

export type MarketStats = {
  top_in: TransferMover[];
  top_out: TransferMover[];
  risers: PriceMover[];
  fallers: PriceMover[];
  movers_24h: NetMover[];
  likely_to_rise: PressureRow[];
  likely_to_fall: PressureRow[];
  total_players: number;
  caveat: string;
};

export type FormRow = StatPlayer & {
  recent_points: number;
  form: number;
  xgi90: number;
};

export type VarianceRow = StatPlayer & {
  goals: number;
  assists: number;
  xg: number;
  xgi: number;
  xgi_delta: number;
  xg_delta: number;
};

export type DiffRow = StatPlayer & { proj: number };

export type DefensiveRow = StatPlayer & {
  dc_per_90: number;
  hit_rate: number;
  threshold: number;
  dc_hits: number;
  dc_starts: number;
};

export type BonusRow = StatPlayer & {
  bonus: number;
  bps90: number;
  bonus_per_start: number;
};

export type SetPiecePlayer = { id: number; web_name: string; order: number };

export type SetPieceTeam = {
  team_id: number;
  team_short: string;
  penalties: SetPiecePlayer[];
  corners: SetPiecePlayer[];
  freekicks: SetPiecePlayer[];
};

export type InsightsStats = {
  in_form: FormRow[];
  underperformers: VarianceRow[];
  overperformers: VarianceRow[];
  differentials: DiffRow[];
  defensive: DefensiveRow[];
  bonus: BonusRow[];
  set_pieces: SetPieceTeam[];
};

export type FixtureChip = { opponent: string; fdr: number; is_home: boolean };

export type CaptaincyRow = StatPlayer & {
  proj: number;
  status: string;
  chance_of_playing_next_round: number | null;
  is_captain: boolean;
  is_vice_captain: boolean;
  fixtures: FixtureChip[];
};

export type CrowdCaptain = {
  event: number;
  id: number;
  web_name: string;
  team_short: string;
  event_points: number;
};

export type ThreatRow = StatPlayer & { proj: number; threat: number };

export type SquadStats = {
  captaincy: { board: CaptaincyRow[]; gap: number; crowd: CrowdCaptain | null };
  template_threats: ThreatRow[];
  differentials: DiffRow[];
  ownership: {
    xi_avg_ownership: number;
    template_count: number;
    differential_count: number;
    squad_size: number;
  };
};

export type SeasonGwRow = {
  event: number;
  points: number;
  total_points: number;
  average: number | null;
  delta_vs_avg: number | null;
  highest: number | null;
  rank: number | null;
  overall_rank: number | null;
  percentile_rank: number | null;
  points_on_bench: number;
  transfers: number;
  hit_cost: number;
  value: number;
  chip: string | null;
};

export type SeasonSummary = {
  best_gw: { event: number; points: number } | null;
  worst_gw: { event: number; points: number } | null;
  gws_above_average: number;
  bench_points_total: number;
  hit_cost_total: number;
  latest_percentile: number | null;
  latest_overall_rank: number | null;
  total_points: number;
};

export type CaptainReturnRow = {
  event: number;
  captain_id: number;
  captain_name: string;
  multiplier: number;
  points: number;
  crowd_id: number | null;
  crowd_name: string | null;
  crowd_points: number;
  delta: number;
};

export type SeasonStats = {
  rows: SeasonGwRow[];
  summary: SeasonSummary;
  captain_returns: { rows: CaptainReturnRow[]; total: number; crowd_total: number };
};
