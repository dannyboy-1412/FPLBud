import vm from "node:vm";
import { describe, expect, it } from "vitest";
import {
  EDITION_BOOT_SCRIPT,
  EDITION_KEY,
  EDITION_MAX_AGE,
  editionCookie,
  storedEdition,
} from "./edition";

function boot(local: string | null, cookie: string) {
  const attrs = new Map<string, string>();
  const store: Record<string, string> = {};
  if (local !== null) store[EDITION_KEY] = local;
  let jar = cookie;
  const context = {
    localStorage: {
      getItem: (key: string) => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null),
      setItem: (key: string, value: string) => {
        store[key] = value;
      },
    },
    document: {
      documentElement: {
        setAttribute: (name: string, value: string) => {
          attrs.set(name, value);
        },
        removeAttribute: (name: string) => {
          attrs.delete(name);
        },
      },
      get cookie() {
        return jar;
      },
      set cookie(value: string) {
        const pair = value.split(";")[0] ?? "";
        const eq = pair.indexOf("=");
        const name = pair.slice(0, eq).trim();
        const next = pair.slice(eq + 1).trim();
        const parts = jar
          .split("; ")
          .filter((part) => part.length > 0 && !part.startsWith(`${name}=`));
        parts.push(`${name}=${next}`);
        jar = parts.join("; ");
      },
    },
  };
  vm.runInNewContext(EDITION_BOOT_SCRIPT, context);
  return { attrs, store, jar };
}

const CASES: Array<[string | null, string]> = [
  ["evening", ""],
  ["morning", ""],
  ["evening", "edition=morning"],
  [null, "edition=evening"],
  [null, "theme=dark; edition=evening"],
  [null, "edition=evening; theme=dark"],
  [null, ""],
  [null, "edition=eveningish"],
  [null, "edition=<script>"],
  ["night", "edition=evening"],
  ["night", ""],
];

describe("stored edition", () => {
  it("prefers local storage, then a morning or evening cookie", () => {
    expect(storedEdition("evening", "edition=morning")).toBe("evening");
    expect(storedEdition("morning", "")).toBe("morning");
    expect(storedEdition(null, "theme=dark; edition=evening")).toBe("evening");
    expect(storedEdition(null, "edition=evening; theme=dark")).toBe("evening");
    expect(storedEdition(null, "")).toBeNull();
    expect(storedEdition("night", "")).toBeNull();
    expect(storedEdition(null, "edition=eveningish")).toBeNull();
    expect(storedEdition(null, "edition=<script>")).toBeNull();
    expect(storedEdition("night", "edition=morning")).toBe("morning");
  });

  it("writes a one-year cookie the boot script can read", () => {
    expect(editionCookie("evening")).toBe(
      `edition=evening; Path=/; Max-Age=${EDITION_MAX_AGE}; SameSite=Lax`,
    );
    expect(EDITION_MAX_AGE).toBe(31536000);
  });
});

describe("edition boot script", () => {
  it.each(CASES)("applies %j with cookie %j before paint", (local, cookie) => {
    const result = boot(local, cookie);
    const expected = storedEdition(local, cookie);
    if (expected === "evening") {
      expect(result.attrs.get("data-edition")).toBe("evening");
    } else {
      expect(result.attrs.has("data-edition")).toBe(false);
    }
    if (!expected) {
      expect(result.jar).toBe(cookie);
      expect(result.store[EDITION_KEY]).toBe(local ?? undefined);
      return;
    }
    expect(result.store[EDITION_KEY]).toBe(expected);
    expect(result.jar).toContain(`${EDITION_KEY}=${expected}`);
  });
});
