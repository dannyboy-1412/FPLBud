import "server-only";

import { cacheLife, cacheTag } from "next/cache";
import { connection } from "next/server";
import { cache } from "react";
import {
  api,
  ApiError,
  TeamNotFoundError,
  type InsightsStats,
  type MeResponse,
  type Meta,
  type PlayerRow,
  type PublicTeam,
  type SquadStats,
} from "@/lib/api";
import {
  messageFrom,
  threadFrom,
  usageFrom,
  type ChatUsage,
  type StoredMessage,
  type StoredThread,
} from "@/lib/chat";
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

const PUBLIC_TEAM_SHAPE = 8;

async function fetchPublicTeam(
  entryId: number,
  _shape: number,
): Promise<PublicTeam | { notFound: true }> {
  "use cache";
  cacheLife({ stale: 60, revalidate: 300, expire: 3600 });
  cacheTag(`team:${entryId}:v${_shape}`);
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
  const result = await fetchPublicTeam(entryId, PUBLIC_TEAM_SHAPE);
  if ("notFound" in result) {
    throw new TeamNotFoundError(entryId);
  }
  return result;
}

type PlayerFilters = {
  position?: number;
  maxCost: number;
  horizon: number;
  limit?: number;
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
  if (filters.limit) q.set("limit", String(filters.limit));
  return api<{ players: PlayerRow[] }>(`/players?${q}`, { token });
}

const POSITION_IDS = [1, 2, 3, 4] as const;

export async function getPositionLeaders(): Promise<Record<number, PlayerRow[]>> {
  const lists = await Promise.all(
    POSITION_IDS.map((position) => getPlayers({ position, maxCost: 150, horizon: 1, limit: 5 })),
  );
  return Object.fromEntries(POSITION_IDS.map((position, index) => [position, lists[index].players]));
}

async function getPlayers(filters: PlayerFilters): Promise<{ players: PlayerRow[] }> {
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

export async function getOwnedIds(): Promise<number[]> {
  try {
    const team = await getMyTeam();
    return team?.squad_players.map((p) => p.element) ?? [];
  } catch (err) {
    if (err instanceof TeamNotFoundError) return [];
    throw err;
  }
}

export const getMySquadStats = cache(async (): Promise<SquadStats> => {
  const token = await getAccessToken();
  if (!token) throw new ApiError(401, "sign in required");
  return api<SquadStats>("/me/stats/squad", { token });
});

export const getInsights = cache(async (position?: number): Promise<InsightsStats> => {
  const token = await getAccessToken();
  if (!token) throw new ApiError(401, "sign in required");
  const q = new URLSearchParams();
  if (position) q.set("position", String(position));
  const query = q.toString();
  return api<InsightsStats>(query ? `/stats/insights?${query}` : "/stats/insights", { token });
});

export type ChatListResult =
  | { status: "ok"; threads: StoredThread[] }
  | { status: "disabled" }
  | { status: "error"; message: string };

export type ChatThreadResult =
  | { status: "ok"; thread: StoredThread; messages: StoredMessage[] }
  | { status: "missing" }
  | { status: "disabled" }
  | { status: "error"; message: string };

export async function getChatThreads(): Promise<ChatListResult> {
  const token = await getAccessToken();
  if (!token) return { status: "error", message: "Sign in required." };
  try {
    const body = await api<{ threads: unknown }>("/chat/threads", { token });
    const threads = Array.isArray(body.threads) ? body.threads.flatMap((row) => {
      const thread = threadFrom(row);
      return thread ? [thread] : [];
    }) : [];
    return { status: "ok", threads };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return { status: "ok", threads: [] };
    return chatFailure(err, "The notebook could not be loaded.");
  }
}

export async function getChatThread(id: string): Promise<ChatThreadResult> {
  const token = await getAccessToken();
  if (!token) return { status: "error", message: "Sign in required." };
  try {
    const body = await api<{ thread: unknown; messages: unknown }>(
      `/chat/threads/${encodeURIComponent(id)}`,
      { token },
    );
    const thread = threadFrom(body.thread);
    if (!thread) return { status: "error", message: "That conversation could not be read." };
    const messages = Array.isArray(body.messages)
      ? body.messages.flatMap((row) => {
          const message = messageFrom(row);
          return message ? [message] : [];
        })
      : [];
    return { status: "ok", thread, messages };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return { status: "missing" };
    const failed = chatFailure(err, "That conversation could not be loaded.");
    if (failed.status === "disabled") return failed;
    return failed;
  }
}

export async function getChatUsage(): Promise<ChatUsage | null> {
  const token = await getAccessToken();
  if (!token) return null;
  try {
    return usageFrom(await api<unknown>("/chat/usage", { token }));
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 503)) return null;
    return null;
  }
}

function chatFailure(err: unknown, fallback: string): { status: "disabled" } | { status: "error"; message: string } {
  if (err instanceof ApiError && err.status === 503) return { status: "disabled" };
  if (err instanceof ApiError && err.status === 404) return { status: "error", message: fallback };
  return { status: "error", message: fallback };
}

