import { describe, expect, it } from "vitest";
import {
  boardFrom,
  defaultScope,
  insightsHref,
  matchingPosition,
  nextSort,
  positionFrom,
  sortRows,
  visibleBoard,
  type ColumnSort,
} from "./insights-view";

function player(id: number, position = 3) {
  return { id, position_id: position };
}

describe("insights view", () => {
  it("reads a position and a board from the query", () => {
    expect(positionFrom("2")).toBe(2);
    expect(positionFrom(["4", "1"])).toBe(4);
    expect(positionFrom("9")).toBeUndefined();
    expect(positionFrom(undefined)).toBeUndefined();
    expect(boardFrom("bonus")).toBe("bonus");
    expect(boardFrom(["set_pieces"])).toBe("set_pieces");
    expect(boardFrom("nope")).toBe("in_form");
  });

  it("hides set pieces while a position is selected", () => {
    expect(visibleBoard("set_pieces", true)).toBe("in_form");
    expect(visibleBoard("set_pieces", false)).toBe("set_pieces");
    expect(visibleBoard("bonus", true)).toBe("bonus");
  });

  it("keeps the board on position links and omits the default board", () => {
    expect(insightsHref(undefined, "in_form")).toBe("/dashboard/insights");
    expect(insightsHref(2, "in_form")).toBe("/dashboard/insights?pos=2");
    expect(insightsHref(undefined, "bonus")).toBe("/dashboard/insights?board=bonus");
    expect(insightsHref(2, "defensive")).toBe("/dashboard/insights?pos=2&board=defensive");
  });

  it("keeps only the selected position", () => {
    const rows = [player(1, 2), player(2, 3)];
    expect(matchingPosition(rows, 2)?.map((row) => row.id)).toEqual([1]);
    expect(matchingPosition(rows, undefined)).toBe(rows);
    expect(matchingPosition(undefined, 2)).toBeUndefined();
  });

  it("opens on the squad when a team is saved", () => {
    expect(defaultScope(true)).toBe("squad");
    expect(defaultScope(false)).toBe("league");
  });

  it("sorts a copy and steps back to the server order", () => {
    const rows = [
      { name: "Saka", points: 2 },
      { name: "Haaland", points: 5 },
      { name: "Saka", points: 2 },
    ];
    expect(sortRows(rows, (row) => row.points, "desc").map((row) => row.name)).toEqual(["Haaland", "Saka", "Saka"]);
    expect(sortRows(rows, (row) => row.name, "asc").map((row) => row.points)).toEqual([5, 2, 2]);
    expect(rows.map((row) => row.name)).toEqual(["Saka", "Haaland", "Saka"]);

    let sort: ColumnSort | null = null;
    sort = nextSort(sort, "points", "desc");
    expect(sort).toEqual({ key: "points", direction: "desc" });
    sort = nextSort(sort, "points", "desc");
    expect(sort).toEqual({ key: "points", direction: "asc" });
    sort = nextSort(sort, "points", "desc");
    expect(sort).toBeNull();
    expect(nextSort({ key: "points", direction: "desc" }, "name", "asc")).toEqual({ key: "name", direction: "asc" });
  });
});
