"use client";

import { useState, type ReactNode } from "react";
import type { BonusRow, DefensiveRow, DiffRow, FormRow, InsightsStats, SetPiecePlayer, SetPieceTeam } from "@/lib/api";
import { tabPanelId, tabTriggerId, Tabs, type TabOption } from "@/components/programme/Tabs";
import { price } from "./format";
import {
  BOARD_PREVIEW_ROWS,
  nextSort,
  sortRows,
  visibleBoard,
  type BoardId,
  type ColumnSort,
  type PositionId,
  type SortDirection,
} from "./insights-view";
import { MetricBar, PlayerCell } from "./StatTable";

const BOARD_TABS: TabOption<BoardId>[] = [
  { id: "in_form", label: "In form" },
  { id: "differentials", label: "Differentials" },
  { id: "defensive", label: "Defensive" },
  { id: "bonus", label: "Bonus" },
  { id: "set_pieces", label: "Set pieces" },
];

const BOARD_COPY: Record<BoardId, string> = {
  in_form: "Recent returns among players with enough minutes.",
  differentials: "Under 10% owned, ranked with your weights.",
  defensive: "How often they clear the FPL defensive-contribution threshold.",
  bonus: "Season bonus, bonus points per 90, and bonus per start.",
  set_pieces: "Penalty, corner and direct free-kick order.",
};

type Column<T> = {
  id: string;
  header: string;
  align: "start" | "end";
  first: SortDirection;
  sortValue: (row: T) => number | string;
  magnitude?: (row: T) => number;
  cell: (row: T, max: number) => ReactNode;
};

function ariaSort(sort: ColumnSort | null, id: string): "ascending" | "descending" | "none" {
  if (sort?.key !== id) return "none";
  return sort.direction === "asc" ? "ascending" : "descending";
}

function TakerList({ takers, ownedIds }: { takers: SetPiecePlayer[]; ownedIds: number[] }) {
  if (takers.length === 0) return <>—</>;
  return (
    <>
      {takers.map((taker, index) => (
        <span key={taker.id}>
          {index > 0 ? ", " : null}
          {taker.web_name}
          {ownedIds.includes(taker.id) ? <span className="caption ml-1">you own</span> : null}
        </span>
      ))}
    </>
  );
}

function takerNames(takers: SetPiecePlayer[]) {
  return takers.map((taker) => taker.web_name).join(", ");
}

function inFormColumns(ownedIds: number[]): Column<FormRow>[] {
  return [
    {
      id: "player",
      header: "Player",
      align: "start",
      first: "asc",
      sortValue: (row) => row.web_name,
      cell: (row) => <PlayerCell player={row} ownedIds={ownedIds} />,
    },
    {
      id: "points",
      header: "Pts",
      align: "end",
      first: "desc",
      sortValue: (row) => row.recent_points,
      magnitude: (row) => row.recent_points,
      cell: (row, max) => <MetricBar value={row.recent_points} max={max} label={String(row.recent_points)} />,
    },
    {
      id: "form",
      header: "Form",
      align: "end",
      first: "desc",
      sortValue: (row) => row.form,
      cell: (row) => row.form.toFixed(1),
    },
    {
      id: "xgi",
      header: "xGI/90",
      align: "end",
      first: "desc",
      sortValue: (row) => row.xgi90,
      cell: (row) => row.xgi90.toFixed(2),
    },
  ];
}

function differentialColumns(ownedIds: number[]): Column<DiffRow>[] {
  return [
    {
      id: "player",
      header: "Player",
      align: "start",
      first: "asc",
      sortValue: (row) => row.web_name,
      cell: (row) => <PlayerCell player={row} ownedIds={ownedIds} />,
    },
    {
      id: "own",
      header: "Own%",
      align: "end",
      first: "desc",
      sortValue: (row) => row.selected_by_percent,
      cell: (row) => `${row.selected_by_percent.toFixed(1)}%`,
    },
    {
      id: "proj",
      header: "Proj",
      align: "end",
      first: "desc",
      sortValue: (row) => row.proj,
      magnitude: (row) => row.proj,
      cell: (row, max) => <MetricBar value={row.proj} max={max} label={row.proj.toFixed(1)} />,
    },
    {
      id: "price",
      header: "Price",
      align: "end",
      first: "desc",
      sortValue: (row) => row.now_cost,
      cell: (row) => price(row.now_cost),
    },
  ];
}

function defensiveColumns(ownedIds: number[]): Column<DefensiveRow>[] {
  return [
    {
      id: "player",
      header: "Player",
      align: "start",
      first: "asc",
      sortValue: (row) => row.web_name,
      cell: (row) => <PlayerCell player={row} ownedIds={ownedIds} />,
    },
    {
      id: "hit",
      header: "Hit%",
      align: "end",
      first: "desc",
      sortValue: (row) => row.hit_rate,
      magnitude: (row) => row.hit_rate,
      cell: (row, max) => <MetricBar value={row.hit_rate} max={max} label={`${Math.round(row.hit_rate * 100)}%`} />,
    },
    {
      id: "rate",
      header: "DC/90",
      align: "end",
      first: "desc",
      sortValue: (row) => row.dc_per_90,
      cell: (row) => row.dc_per_90.toFixed(1),
    },
    {
      id: "hits",
      header: "Hits",
      align: "end",
      first: "desc",
      sortValue: (row) => row.dc_hits,
      cell: (row) => `${row.dc_hits}/${row.dc_starts}`,
    },
  ];
}

function bonusColumns(ownedIds: number[]): Column<BonusRow>[] {
  return [
    {
      id: "player",
      header: "Player",
      align: "start",
      first: "asc",
      sortValue: (row) => row.web_name,
      cell: (row) => <PlayerCell player={row} ownedIds={ownedIds} />,
    },
    {
      id: "bonus",
      header: "Bonus",
      align: "end",
      first: "desc",
      sortValue: (row) => row.bonus,
      magnitude: (row) => row.bonus,
      cell: (row, max) => <MetricBar value={row.bonus} max={max} label={String(row.bonus)} />,
    },
    {
      id: "bps",
      header: "BPS/90",
      align: "end",
      first: "desc",
      sortValue: (row) => row.bps90,
      cell: (row) => row.bps90.toFixed(1),
    },
    {
      id: "start",
      header: "Per start",
      align: "end",
      first: "desc",
      sortValue: (row) => row.bonus_per_start,
      cell: (row) => row.bonus_per_start.toFixed(2),
    },
  ];
}

function setPieceColumns(ownedIds: number[]): Column<SetPieceTeam>[] {
  return [
    {
      id: "club",
      header: "Club",
      align: "start",
      first: "asc",
      sortValue: (row) => row.team_short,
      cell: (row) => row.team_short,
    },
    {
      id: "penalties",
      header: "Penalties",
      align: "start",
      first: "asc",
      sortValue: (row) => takerNames(row.penalties),
      cell: (row) => <TakerList takers={row.penalties} ownedIds={ownedIds} />,
    },
    {
      id: "corners",
      header: "Corners",
      align: "start",
      first: "asc",
      sortValue: (row) => takerNames(row.corners),
      cell: (row) => <TakerList takers={row.corners} ownedIds={ownedIds} />,
    },
    {
      id: "freekicks",
      header: "Free kicks",
      align: "start",
      first: "asc",
      sortValue: (row) => takerNames(row.freekicks),
      cell: (row) => <TakerList takers={row.freekicks} ownedIds={ownedIds} />,
    },
  ];
}

function ActiveTable({
  shown,
  insights,
  ownedIds,
}: {
  shown: BoardId;
  insights: InsightsStats;
  ownedIds: number[];
}) {
  const [sort, setSort] = useState<ColumnSort | null>(null);
  const [expanded, setExpanded] = useState(false);

  function onSort(column: { id: string; first: SortDirection }) {
    setSort((current) => nextSort(current, column.id, column.first));
  }

  const shared = {
    sort,
    onSort,
    expanded,
    onToggle: () => setExpanded((open) => !open),
  };

  if (shown === "in_form") {
    return <BoardTable rows={insights.in_form} columns={inFormColumns(ownedIds)} rowKey={(row) => row.id} {...shared} />;
  }
  if (shown === "differentials") {
    return (
      <BoardTable rows={insights.differentials} columns={differentialColumns(ownedIds)} rowKey={(row) => row.id} {...shared} />
    );
  }
  if (shown === "defensive") {
    return (
      <BoardTable rows={insights.defensive} columns={defensiveColumns(ownedIds)} rowKey={(row) => row.id} {...shared} />
    );
  }
  if (shown === "bonus") {
    return <BoardTable rows={insights.bonus} columns={bonusColumns(ownedIds)} rowKey={(row) => row.id} {...shared} />;
  }
  return (
    <BoardTable rows={insights.set_pieces} columns={setPieceColumns(ownedIds)} rowKey={(row) => row.team_id} {...shared} />
  );
}

function BoardTable<T>({
  rows,
  columns,
  rowKey,
  sort,
  onSort,
  expanded,
  onToggle,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  sort: ColumnSort | null;
  onSort: (column: Column<T>) => void;
  expanded: boolean;
  onToggle: () => void;
}) {
  if (rows.length === 0) return <p className="insight-note">Nothing to show yet.</p>;
  const active = columns.find((column) => column.id === sort?.key);
  const ordered = sort == null || active == null ? rows : sortRows(rows, active.sortValue, sort.direction);
  const shown = expanded ? ordered : ordered.slice(0, BOARD_PREVIEW_ROWS);
  const peaks = new Map(
    columns.map((column) => [
      column.id,
      column.magnitude == null ? 0 : rows.reduce((max, row) => Math.max(max, column.magnitude?.(row) ?? 0), 0),
    ]),
  );

  return (
    <div className="overflow-x-auto">
      <table className="insight-table w-full text-sm nums">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.id}
                aria-sort={ariaSort(sort, column.id)}
                className={column.align === "end" ? "text-right" : "text-left"}
              >
                <button type="button" className="insight-sort" onClick={() => onSort(column)}>
                  {column.header}
                  {sort?.key === column.id ? <span aria-hidden>{sort.direction === "asc" ? " ↑" : " ↓"}</span> : null}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.id} className={column.align === "end" ? "text-right whitespace-nowrap" : ""}>
                  {column.cell(row, peaks.get(column.id) ?? 0)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > BOARD_PREVIEW_ROWS ? (
        <button type="button" className="insight-more" aria-expanded={expanded} onClick={onToggle}>
          {expanded ? "Show less" : "Show all"}
        </button>
      ) : null}
    </div>
  );
}

export function InsightsBoards({
  insights,
  ownedIds,
  position,
  board,
  onBoard,
}: {
  insights: InsightsStats;
  ownedIds: number[];
  position: PositionId | undefined;
  board: BoardId;
  onBoard: (board: BoardId) => void;
}) {
  const shown = visibleBoard(board, position != null);
  const tabs = position == null ? BOARD_TABS : BOARD_TABS.filter((tab) => tab.id !== "set_pieces");

  return (
    <section className="insight-card">
      <div className="insight-card-head">
        <div>
          <p className="insight-title">Rankings</p>
          <p className="insight-note">{BOARD_COPY[shown]}</p>
        </div>
      </div>
      <Tabs name="boards" label="Insight boards" tabs={tabs} value={shown} onChange={onBoard} wide />
      <div role="tabpanel" id={tabPanelId("boards")} aria-labelledby={tabTriggerId("boards", shown)} className="mt-2">
        <ActiveTable key={`${shown}:${position ?? "all"}`} shown={shown} insights={insights} ownedIds={ownedIds} />
      </div>
    </section>
  );
}
