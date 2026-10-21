export const POS = ["", "GKP", "DEF", "MID", "FWD"];

export function pounds(tenths: number) {
  return `£${(tenths / 10).toFixed(1)}m`;
}

export function compact(n: number) {
  const abs = Math.abs(n);
  const sign = n < 0 ? "−" : "";
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(2)}m`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(1)}k`;
  return `${sign}${abs}`;
}

export function costDelta(tenths: number) {
  const sign = tenths > 0 ? "+" : tenths < 0 ? "−" : "";
  return `${sign}${(Math.abs(tenths) / 10).toFixed(1)}`;
}

export function signed(n: number, digits = 1) {
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}${Math.abs(n).toFixed(digits)}`;
}

export function rankLabel(n: number | null) {
  if (n == null) return "—";
  return n.toLocaleString();
}
