export const POS = ["", "GKP", "DEF", "MID", "FWD"];

export const POSITIONS = [
  { id: 1, label: "Goalkeeper" },
  { id: 2, label: "Defender" },
  { id: 3, label: "Midfielder" },
  { id: 4, label: "Striker" },
] as const;

export function price(tenths: number) {
  return `£${(tenths / 10).toFixed(1)}`;
}

export function signed(n: number, digits = 1) {
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}${Math.abs(n).toFixed(digits)}`;
}
