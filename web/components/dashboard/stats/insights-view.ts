export const PREVIEW_ROWS = 5;
export const BOARD_PREVIEW_ROWS = 10;

export const POSITION_IDS = [1, 2, 3, 4] as const;
export type PositionId = (typeof POSITION_IDS)[number];

export const BOARD_IDS = ["in_form", "differentials", "defensive", "bonus", "set_pieces"] as const;
export type BoardId = (typeof BOARD_IDS)[number];

export type AttentionScope = "squad" | "league";
export type SortDirection = "asc" | "desc";
export type ColumnSort = { key: string; direction: SortDirection };

export function positionFrom(raw: string | string[] | undefined): PositionId | undefined {
  const value = Array.isArray(raw) ? raw[0] : raw;
  const id = Number(value);
  return POSITION_IDS.find((position) => position === id);
}

export function boardFrom(raw: string | string[] | undefined): BoardId {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return BOARD_IDS.find((board) => board === value) ?? "in_form";
}

export function visibleBoard(board: BoardId, positionSelected: boolean): BoardId {
  if (board === "set_pieces" && positionSelected) return "in_form";
  return board;
}

export function insightsHref(position: PositionId | undefined, board: BoardId) {
  const params = new URLSearchParams();
  if (position != null) params.set("pos", String(position));
  if (board !== "in_form") params.set("board", board);
  const query = params.toString();
  return query ? `/dashboard/insights?${query}` : "/dashboard/insights";
}

export function matchingPosition<T extends { position_id: number }>(
  rows: T[] | undefined,
  position: number | undefined,
): T[] | undefined {
  if (rows == null || position == null) return rows;
  return rows.filter((row) => row.position_id === position);
}

export function defaultScope(hasTeam: boolean): AttentionScope {
  return hasTeam ? "squad" : "league";
}

export function sortRows<T>(
  rows: readonly T[],
  value: (row: T) => number | string,
  direction: SortDirection,
): T[] {
  const copy = [...rows];
  copy.sort((left, right) => {
    const a = value(left);
    const b = value(right);
    const compared = typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b));
    return direction === "asc" ? compared : -compared;
  });
  return copy;
}

export function nextSort(current: ColumnSort | null, key: string, first: SortDirection): ColumnSort | null {
  if (current?.key !== key) return { key, direction: first };
  if (current.direction === first) {
    return { key, direction: first === "asc" ? "desc" : "asc" };
  }
  return null;
}
