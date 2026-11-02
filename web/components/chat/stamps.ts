const LONDON = "Europe/London";

export function clockTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: LONDON,
  });
}

export function shortWhen(iso: string | null, now = new Date()): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  if (londonDay(date) === londonDay(now)) return clockTime(iso);
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: LONDON });
}

export function londonStamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: LONDON,
  });
}

export type ThreadBucket = "today" | "week" | "earlier";

export function threadBucket(iso: string | null, now = new Date()): ThreadBucket {
  if (!iso) return "earlier";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "earlier";
  const day = londonDay(date);
  const today = londonDay(now);
  if (!day || !today) return "earlier";
  if (day === today) return "today";
  const [year, month, dateNum] = today.split("-").map(Number);
  const weekday = londonWeekday(now);
  if (year == null || month == null || dateNum == null || weekday < 0) return "earlier";
  const weekStart = shiftDay(year, month, dateNum, -((weekday + 6) % 7));
  if (day >= weekStart) return "week";
  return "earlier";
}

function londonDay(date: Date): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  const year = value("year");
  const month = value("month");
  const day = value("day");
  if (!year || !month || !day) return "";
  return `${year}-${month}-${day}`;
}

function londonWeekday(date: Date): number {
  const name = new Intl.DateTimeFormat("en-GB", { timeZone: LONDON, weekday: "short" }).format(date);
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(name.slice(0, 3));
}

function shiftDay(year: number, month: number, day: number, delta: number): string {
  const shifted = new Date(Date.UTC(year, month - 1, day + delta));
  const y = shifted.getUTCFullYear();
  const m = String(shifted.getUTCMonth() + 1).padStart(2, "0");
  const d = String(shifted.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
