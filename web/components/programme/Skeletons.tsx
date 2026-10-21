export function HeadingSkeleton() {
  return (
    <div className="flex justify-between items-end gap-4 mb-6">
      <div className="flex-1">
        <div className="skeleton h-3 w-28 mb-3" />
        <div className="skeleton h-10 w-64" />
      </div>
      <div className="skeleton h-11 w-32" />
    </div>
  );
}

export function PitchSkeleton() {
  return (
    <div className="pitch-unit" aria-hidden>
      <div className="pitch">
        <div className="pitch-rows">
          {[1, 4, 4, 2].map((count, row) => (
            <div key={row} className="pitch-row">
              {Array.from({ length: count }, (_, i) => (
                <div key={i} className="pitch-card">
                  <div className="skeleton h-8 w-8 rounded-sm mx-auto" />
                  <div className="skeleton h-12 w-full mt-1" />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="pitch-subs">
        <div className="skeleton h-3 w-24 mb-3" />
        <div className="pitch-row">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="skeleton h-16 w-[74px]" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function TeamSheetSkeleton() {
  return (
    <aside>
      <div className="skeleton h-3 w-24 mb-4" />
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="flex justify-between py-3 border-b border-rule">
          <div className="skeleton h-3 w-28" />
          <div className="skeleton h-6 w-16" />
        </div>
      ))}
    </aside>
  );
}

export function PlanSkeleton() {
  return (
    <div className="mt-8" aria-hidden>
      <div className="skeleton h-3 w-40 mb-3" />
      <div className="skeleton h-8 w-80 mb-4" />
      <div className="flex gap-8 my-4">
        <div className="skeleton h-14 w-24" />
        <div className="skeleton h-10 w-16" />
        <div className="skeleton h-10 w-20" />
      </div>
      <div className="skeleton h-20 w-full mb-4" />
      <div className="skeleton h-32 w-full max-w-[62ch]" />
    </div>
  );
}

export function TableSkeleton() {
  return (
    <div className="space-y-2" aria-hidden>
      {Array.from({ length: 12 }, (_, i) => (
        <div key={i} className="skeleton h-11 w-full" />
      ))}
    </div>
  );
}

export function SettingsSkeleton() {
  return (
    <div className="mt-8 space-y-4" aria-hidden>
      <div className="skeleton h-3 w-40" />
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="skeleton h-16 w-full" />
      ))}
    </div>
  );
}

export function BroadsheetSkeleton() {
  return (
    <div className="broadsheet">
      <PitchSkeleton />
      <div className="col-rule" />
      <TeamSheetSkeleton />
    </div>
  );
}

export function StatsSkeleton() {
  return (
    <div className="grid md:grid-cols-2 gap-x-12 gap-y-8 mt-4" aria-hidden>
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="space-y-2">
          <div className="skeleton h-3 w-28 mb-3" />
          {Array.from({ length: 6 }, (_, j) => (
            <div key={j} className="skeleton h-11 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}
