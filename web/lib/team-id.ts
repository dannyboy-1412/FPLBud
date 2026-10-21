export type ParseTeamIdFailure = "empty" | "invalid";

export type ParseTeamIdResult =
  | { ok: true; id: number }
  | { ok: false; reason: ParseTeamIdFailure };

export type TeamLookupError = ParseTeamIdFailure | "not_found" | "unreachable";

const ENTRY_IN_URL = /\/entry\/(\d{1,8})(?:\/|$|\?)/i;

export function parseTeamId(raw: string): ParseTeamIdResult {
  const trimmed = raw.trim();
  if (!trimmed) return { ok: false, reason: "empty" };
  const fromUrl = trimmed.match(ENTRY_IN_URL);
  const digits = fromUrl ? fromUrl[1] : trimmed;
  if (!/^\d{1,8}$/.test(digits)) return { ok: false, reason: "invalid" };
  const id = Number(digits);
  if (id < 1) return { ok: false, reason: "invalid" };
  return { ok: true, id };
}

export function teamIdErrorMessage(error: TeamLookupError): string {
  switch (error) {
    case "empty":
      return "Enter your team ID";
    case "invalid":
      return "That doesn't look like a team ID; it's the number in your Points page URL.";
    case "not_found":
      return "No team with that ID. Check the number in your Points page URL.";
    case "unreachable":
      return "We can't reach the press room right now.";
  }
}
