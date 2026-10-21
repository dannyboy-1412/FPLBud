import "server-only";

import { cacheLife, cacheTag } from "next/cache";
import { connection } from "next/server";
import { cache } from "react";
import {
  api,
  ApiError,
  TeamNotFoundError,
  type AgentRun,
  type InsightsStats,
  type MarketStats,
  type MeResponse,
  type Meta,
  type PlayerRow,
  type PublicTeam,
  type SeasonStats,
  type SquadStats,
  type TeamReport,
  type Weights,
} from "@/lib/api";
import { getAccessToken } from "@/lib/server/session";

async function getMeta(): Promise<Meta> {
  "use cache";
  cacheLife("minutes");
  cacheTag("meta");
  return api<Meta>("/meta");
}

export async function loadMeta(): Promise<Meta> {
  await connection();
  return getMeta();
}

async function fetchPublicTeam(entryId: number): Promise<PublicTeam | { notFound: true }> {
  "use cache";
  cacheLife({ stale: 60, revalidate: 300, expire: 3600 });
  cacheTag(`team:${entryId}`);
  try {
    return await api<PublicTeam>(`/public/team/${entryId}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return { notFound: true };
    }
    throw err;
  }
}

export async function getPublicTeam(entryId: number): Promise<PublicTeam> {
  const result = await fetchPublicTeam(entryId);
  if ("notFound" in result) {
    throw new TeamNotFoundError(entryId);
  }
  return result;
}

export type PlayerFilters = {
  position?: number;
  maxCost: number;
  horizon: number;
};

async function getPlayersPublic(filters: PlayerFilters): Promise<{ players: PlayerRow[] }> {
  "use cache";
  cacheLife("minutes");
  cacheTag("players");
  return fetchPlayers(filters);
}

async function fetchPlayers(filters: PlayerFilters, token?: string | null): Promise<{ players: PlayerRow[] }> {
  const q = new URLSearchParams();
  if (filters.position) q.set("position", String(filters.position));
  q.set("max_cost", String(filters.maxCost));
  q.set("horizon", String(filters.horizon));
  return api<{ players: PlayerRow[] }>(`/players?${q}`, { token });
}

export async function getPlayers(filters: PlayerFilters): Promise<{ players: PlayerRow[] }> {
  const token = await getAccessToken();
  if (token) return fetchPlayers(filters, token);
  return getPlayersPublic(filters);
}

export const getMe = cache(async (): Promise<MeResponse> => {
  const token = await getAccessToken();
  if (!token) throw new ApiError(401, "sign in required");
  return api<MeResponse>("/me", { token });
});

export const getMyTeam = cache(async (): Promise<PublicTeam | null> => {
  const me = await getMe();
  if (!me.profile.fpl_entry_id) return null;
  return getPublicTeam(me.profile.fpl_entry_id);
});

export const getLatestRun = cache(async (): Promise<AgentRun | null> => {
  const me = await getMe();
  if (!me.latest_run_id) return null;
  return getAgentRun(me.latest_run_id);
});

export async function getOwnedIds(): Promise<number[]> {
  try {
    const team = await getMyTeam();
    return team?.squad_players.map((p) => p.element) ?? [];
  } catch (err) {
    if (err instanceof TeamNotFoundError) return [];
    throw err;
  }
}

async function getMarket(): Promise<MarketStats> {
  "use cache";
  cacheLife("minutes");
  cacheTag("stats");
  return api<MarketStats>("/stats/market");
}

export async function getMarketStats(): Promise<MarketStats> {
  await connection();
  return getMarket();
}

function canonicalWeights(weights: Weights): string {
  return JSON.stringify(
    Object.fromEntries(
      Object.keys(weights)
        .sort()
        .map((key) => [key, Math.round(weights[key as keyof Weights] * 100) / 100]),
    ),
  );
}

async function getInsightsCached(position: number | null, weightsKey: string): Promise<InsightsStats> {
  "use cache";
  cacheLife("minutes");
  cacheTag("stats");
  const q = new URLSearchParams();
  if (position) q.set("position", String(position));
  q.set("weights", weightsKey);
  return api<InsightsStats>(`/stats/insights?${q}`);
}

export async function getInsights(position: number | undefined, weights?: Weights | null): Promise<InsightsStats> {
  return getInsightsCached(position ?? null, weights ? canonicalWeights(weights) : "{}");
}

export const getMySquadStats = cache(async (): Promise<SquadStats> => {
  const token = await getAccessToken();
  if (!token) throw new ApiError(401, "sign in required");
  return api<SquadStats>("/me/stats/squad", { token });
});

export const getMySeason = cache(async (): Promise<SeasonStats> => {
  const token = await getAccessToken();
  if (!token) throw new ApiError(401, "sign in required");
  return api<SeasonStats>("/me/stats/season", { token });
});

export const getTeamReport = cache(async (entryId: number): Promise<TeamReport> => {
  const token = await getAccessToken();
  if (!token) throw new ApiError(401, "sign in required");
  return api<TeamReport>(`/me/report?entry_id=${entryId}`, { token });
});

export async function getAgentRun(runId: number): Promise<AgentRun> {
  const token = await getAccessToken();
  if (!token) throw new ApiError(401, "sign in required");
  return api<AgentRun>(`/agent/runs/${runId}`, { token });
}
