export const EDITION_KEY = "edition";
export const EDITION_MAX_AGE = 60 * 60 * 24 * 365;

export type Edition = "morning" | "evening";

const EDITION_COOKIE_PATTERN = new RegExp(
  `(?:^|; )${EDITION_KEY}=(morning|evening)(?:;|$)`,
);

export function isEdition(value: string | null | undefined): value is Edition {
  return value === "morning" || value === "evening";
}

/** Local storage wins. The cookie covers a full load before storage has been copied across. */
export function storedEdition(local: string | null, cookieHeader: string): Edition | null {
  if (isEdition(local)) return local;
  const match = cookieHeader.match(EDITION_COOKIE_PATTERN);
  return match ? (match[1] as Edition) : null;
}

export function editionCookie(edition: Edition): string {
  return `${EDITION_KEY}=${edition}; Path=/; Max-Age=${EDITION_MAX_AGE}; SameSite=Lax`;
}

export function readStoredEdition(): Edition | null {
  let local: string | null = null;
  try {
    local = window.localStorage.getItem(EDITION_KEY);
  } catch {
    local = null;
  }
  let cookie = "";
  try {
    cookie = document.cookie;
  } catch {
    cookie = "";
  }
  return storedEdition(local, cookie);
}

export function persistEdition(edition: Edition): void {
  try {
    window.localStorage.setItem(EDITION_KEY, edition);
  } catch {
    /* storage unavailable */
  }
  try {
    document.cookie = editionCookie(edition);
  } catch {
    /* cookies unavailable */
  }
}

export function applyEdition(edition: Edition): void {
  if (edition === "evening") {
    document.documentElement.setAttribute("data-edition", "evening");
    return;
  }
  document.documentElement.removeAttribute("data-edition");
}

/**
 * Runs from the root document before first paint.
 * Kept inline so a full load does not wait for the client bundle.
 * localStorage is the existing preference; the cookie is the copy a later load can see.
 */
export const EDITION_BOOT_SCRIPT = `(function(){
  var key = ${JSON.stringify(EDITION_KEY)};
  var edition = null;
  try { edition = localStorage.getItem(key); } catch (e) {}
  if (edition !== "morning" && edition !== "evening") {
    edition = null;
    try {
      var match = document.cookie.match(new RegExp("(?:^|; )" + key + "=(morning|evening)(?:;|$)"));
      if (match) edition = match[1];
    } catch (e) {}
  }
  if (edition !== "morning" && edition !== "evening") return;
  try {
    if (edition === "evening") document.documentElement.setAttribute("data-edition", "evening");
    else document.documentElement.removeAttribute("data-edition");
  } catch (e) {}
  try { localStorage.setItem(key, edition); } catch (e) {}
  try { document.cookie = key + "=" + edition + "; Path=/; Max-Age=${EDITION_MAX_AGE}; SameSite=Lax"; } catch (e) {}
})();`;
