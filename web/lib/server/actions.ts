"use server";

import { cookies } from "next/headers";
import { refresh, updateTag } from "next/cache";
import { redirect } from "next/navigation";
import {
  api,
  ApiError,
  isTeamNotFound,
  type PublicTeam,
  type SuggestedTransfers,
  type SuggestedXi,
  type Weights,
} from "@/lib/api";
import { getPublicTeam } from "@/lib/server/data";
import { getAccessToken } from "@/lib/server/session";
import { PENDING_ENTRY_COOKIE, PENDING_ENTRY_MAX_AGE } from "@/lib/pending-entry";
import { parseTeamId, type TeamLookupError } from "@/lib/team-id";

export async function rememberPendingEntry(entryId: number): Promise<void> {
  const parsed = parseTeamId(String(entryId));
  if (!parsed.ok) return;
  const store = await cookies();
  store.set(PENDING_ENTRY_COOKIE, String(parsed.id), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: PENDING_ENTRY_MAX_AGE,
    secure: process.env.NODE_ENV === "production",
  });
}

export type LookupState =
  | { status: "idle" }
  | { status: "ok"; team: PublicTeam }
  | { status: "error"; error: TeamLookupError };

export async function lookupTeam(_prev: LookupState, formData: FormData): Promise<LookupState> {
  const parsed = parseTeamId(String(formData.get("teamId") ?? ""));
  if (!parsed.ok) return { status: "error", error: parsed.reason };
  try {
    const team = await getPublicTeam(parsed.id);
    return { status: "ok", team };
  } catch (err) {
    if (isTeamNotFound(err)) return { status: "error", error: "not_found" };
    return { status: "error", error: "unreachable" };
  }
}

export type SaveTeamState = { error?: string };

export async function saveTeam(_prev: SaveTeamState, formData: FormData): Promise<SaveTeamState> {
  const parsed = parseTeamId(String(formData.get("entryId") ?? ""));
  if (!parsed.ok) return { error: "That doesn't look like a team ID." };
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    await api("/me/team", {
      method: "PUT",
      token,
      body: JSON.stringify({ entry_id: parsed.id }),
    });
  } catch (err) {
    if (isTeamNotFound(err) || (err instanceof ApiError && err.status === 404)) {
      return { error: "No team with that ID. Check the number in your Points page URL." };
    }
    return { error: "We can't reach the press room right now." };
  }
  updateTag(`team:${parsed.id}`);
  refresh();
  redirect("/dashboard");
}

export type RerunResult = { ok: true; runId: number } | { error: string };

export async function rerunAgent(): Promise<RerunResult> {
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    const result = await api<{ run_id: number }>("/me/agent/rerun", { method: "POST", token });
    refresh();
    return { ok: true, runId: result.run_id };
  } catch (err) {
    if (err instanceof ApiError) return { error: err.message };
    return { error: "We can't reach the press room right now." };
  }
}

export type SaveSettingsState = { error?: string; saved?: boolean };

export async function saveSettings(input: {
  weights: Weights;
  default_horizon: number;
  max_hits: number;
}): Promise<SaveSettingsState> {
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    await api("/me", {
      method: "PUT",
      token,
      body: JSON.stringify({
        weights: input.weights,
        default_horizon: input.default_horizon,
        max_hits: input.max_hits,
      }),
    });
    refresh();
    return { saved: true };
  } catch (err) {
    if (err instanceof ApiError) return { error: err.message };
    return { error: "We can't reach the press room right now." };
  }
}

export async function fetchSuggestedXi(): Promise<{ lineup: SuggestedXi } | { error: string }> {
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    const lineup = await api<SuggestedXi>("/me/suggested-xi", {
      method: "POST",
      token,
      signal: AbortSignal.timeout(60_000),
    });
    return { lineup };
  } catch (err) {
    if (err instanceof ApiError) return { error: err.message };
    return { error: "We can't reach the press room right now." };
  }
}

export async function fetchSuggestedTransfers(): Promise<{ advice: SuggestedTransfers } | { error: string }> {
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    const advice = await api<SuggestedTransfers>("/me/suggested-transfers", {
      method: "POST",
      token,
      signal: AbortSignal.timeout(60_000),
    });
    return { advice };
  } catch (err) {
    if (err instanceof ApiError) return { error: err.message };
    return { error: "We can't reach the press room right now." };
  }
}

export async function sendChatFeedback(
  messageId: number,
  value: 1 | -1,
): Promise<{ error?: string }> {
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    await api(`/chat/messages/${messageId}/feedback`, {
      method: "POST",
      token,
      body: JSON.stringify({ value }),
    });
    return {};
  } catch (err) {
    if (err instanceof ApiError) return { error: err.message };
    return { error: "Could not save feedback." };
  }
}

export async function confirmChatMemory(
  proposalId: number,
  accept: boolean,
): Promise<{ error?: string }> {
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    await api("/chat/memory/confirm", {
      method: "POST",
      token,
      body: JSON.stringify({ proposal_id: proposalId, accept }),
    });
    refresh();
    return {};
  } catch (err) {
    if (err instanceof ApiError) return { error: err.message };
    return { error: "Could not update that preference." };
  }
}

export async function deleteChatMemory(formData: FormData): Promise<void> {
  const token = await getAccessToken();
  if (!token) return;
  const key = String(formData.get("key") ?? "");
  if (!key) return;
  await api(`/chat/memory?key=${encodeURIComponent(key)}`, { method: "DELETE", token });
  refresh();
}

export async function deleteChatHistory(): Promise<{ error?: string }> {
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    await api("/chat/threads", { method: "DELETE", token });
    await api("/chat/memory", { method: "DELETE", token });
    refresh();
    return {};
  } catch (err) {
    if (err instanceof ApiError) return { error: err.message };
    return { error: "Could not delete chat history." };
  }
}

export async function deleteAccount(): Promise<{ error?: string }> {
  const token = await getAccessToken();
  if (!token) return { error: "Sign in required." };
  try {
    await api("/me", { method: "DELETE", token });
    return {};
  } catch {
    return { error: "Could not delete account." };
  }
}
