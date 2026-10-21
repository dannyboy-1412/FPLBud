import { getMarketStats, getOwnedIds } from "@/lib/server/data";
import { compact, costDelta } from "./format";
import { PlayerCell, StatTable } from "./StatTable";

export async function MarketSection() {
  const ownedIdsPromise = getOwnedIds();
  const data = await getMarketStats();
  const ownedIds = await ownedIdsPromise;
  return (
    <div className="grid md:grid-cols-2 gap-x-12 gap-y-10">
      <section>
        <p className="kicker mb-3">Transfers in</p>
        <StatTable
          headers={["Player", "In", "Net", "Own%"]}
          rows={data.top_in.map((p) => ({
            id: `in-${p.id}`,
            cells: [
              <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
              compact(p.transfers_in_event),
              compact(p.net),
              `${p.selected_by_percent.toFixed(1)}%`,
            ],
          }))}
        />
      </section>
      <section>
        <p className="kicker mb-3">Transfers out</p>
        <StatTable
          headers={["Player", "Out", "Net", "Own%"]}
          rows={data.top_out.map((p) => ({
            id: `out-${p.id}`,
            cells: [
              <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
              compact(p.transfers_out_event),
              compact(p.net),
              `${p.selected_by_percent.toFixed(1)}%`,
            ],
          }))}
        />
      </section>
      <section className="md:col-span-2">
        <p className="kicker mb-3">Biggest 24h net movers</p>
        <StatTable
          headers={["Player", "Net 24h", "Price Δ", "Own%"]}
          rows={data.movers_24h.map((p) => ({
            id: `h-${p.id}`,
            cells: [
              <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
              compact(p.net_24h),
              costDelta(p.daily_change),
              `${p.selected_by_percent.toFixed(1)}%`,
            ],
          }))}
        />
      </section>
      <section>
        <p className="kicker mb-3">Price risers</p>
        <StatTable
          headers={["Player", "This GW", "Season", "Own%"]}
          rows={data.risers.map((p) => ({
            id: `r-${p.id}`,
            cells: [
              <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
              costDelta(p.cost_change_event),
              costDelta(p.cost_change_start),
              `${p.selected_by_percent.toFixed(1)}%`,
            ],
          }))}
        />
      </section>
      <section>
        <p className="kicker mb-3">Price fallers</p>
        <StatTable
          headers={["Player", "This GW", "Season", "Own%"]}
          rows={data.fallers.map((p) => ({
            id: `f-${p.id}`,
            cells: [
              <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
              costDelta(p.cost_change_event),
              costDelta(p.cost_change_start),
              `${p.selected_by_percent.toFixed(1)}%`,
            ],
          }))}
        />
      </section>
      <section>
        <p className="kicker mb-3">Likely to rise</p>
        <StatTable
          headers={["Player", "Pressure", "Net", "Own%"]}
          rows={data.likely_to_rise.map((p) => ({
            id: `pr-${p.id}`,
            cells: [
              <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
              p.pressure.toFixed(3),
              compact(p.net),
              `${p.selected_by_percent.toFixed(1)}%`,
            ],
          }))}
        />
      </section>
      <section>
        <p className="kicker mb-3">Likely to fall</p>
        <StatTable
          headers={["Player", "Pressure", "Net", "Own%"]}
          rows={data.likely_to_fall.map((p) => ({
            id: `pf-${p.id}`,
            cells: [
              <PlayerCell key="n" player={p} ownedIds={ownedIds} />,
              p.pressure.toFixed(3),
              compact(p.net),
              `${p.selected_by_percent.toFixed(1)}%`,
            ],
          }))}
        />
      </section>
      <p className="caption md:col-span-2">{data.caveat}</p>
    </div>
  );
}
