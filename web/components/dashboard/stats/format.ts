export const POS = ["", "GKP", "DEF", "MID", "FWD"];

export function signed(n: number, digits = 1) {
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}${Math.abs(n).toFixed(digits)}`;
}
