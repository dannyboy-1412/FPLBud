import type { HorizonPlan } from "@/lib/api";

function pounds(tenths: number) {
  const v = tenths / 10;
  const sign = v >= 0 ? "+" : "−";
  return `${sign}£${Math.abs(v).toFixed(1)}m`;
}

export function PlanArticle({ plan, locked }: { plan: HorizonPlan; locked?: boolean }) {
  const inner = (
    <article className="relative">
      {!locked ? (
        <div className="absolute -top-2 right-0 -rotate-6 border-2 border-vermilion text-vermilion px-2.5 py-1.5 text-[0.7rem] tracking-[0.12em] font-bold bg-paper pointer-events-none">
          AGENT&apos;S PICK
        </div>
      ) : null}
      <p className="kicker">
        {plan.horizon === 1 ? "Next gameweek" : `Next ${plan.horizon} gameweeks`} · Recommended
      </p>
      <h2 className="mt-2">{plan.headline ?? (plan.transfers.length ? "Make these transfers" : "Roll the transfer")}</h2>
      <div className="flex gap-8 items-end my-4">
        <div>
          <div className={`stat-xl ${plan.gain_vs_roll >= 0 ? "text-racing" : "text-claret"}`}>
            {plan.gain_vs_roll >= 0 ? "+" : ""}
            {plan.gain_vs_roll.toFixed(1)}
          </div>
          <p className="caption">projected points vs rolling</p>
        </div>
        <div>
          <div className={`stat ${plan.hits ? "text-claret" : ""}`}>{plan.hits ? `−${plan.hits * 4}` : "No hit"}</div>
          <p className="caption">hit</p>
        </div>
        {plan.bank_after != null ? (
          <div>
            <div className="stat">£{(plan.bank_after / 10).toFixed(1)}m</div>
            <p className="caption">bank after</p>
          </div>
        ) : null}
      </div>
      {plan.transfers.map((t) => (
        <div key={`${t.out}-${t.in}`} className="grid grid-cols-[1fr_1px_1fr_auto] gap-4 py-4 border-y border-rule">
          <div className="text-ink-soft">
            <p className="kicker">Out</p>
            <p className="font-semibold line-through">{t.out_name}</p>
          </div>
          <div className="bg-rule" />
          <div>
            <p className="kicker">In</p>
            <p className="font-semibold">{t.in_name}</p>
          </div>
          <div className="nums self-center">{pounds(t.cost_delta)}</div>
          {t.metric_deltas ? (
            <div className="col-span-4 flex flex-wrap gap-x-5 gap-y-2 text-[0.8125rem]">
              {Object.entries(t.metric_deltas).map(([k, v]) => (
                <span key={k}>
                  <span
                    className={`inline-block h-1.5 align-middle mr-1.5 ${v >= 0 ? "bg-racing" : "bg-claret"}`}
                    style={{ width: `${Math.min(40, Math.abs(v) * 80)}px` }}
                  />
                  {k} {v >= 0 ? "+" : ""}
                  {v.toFixed(2)}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ))}
      <p className="mt-4">
        <span className="kicker">Captain</span>{" "}
        <span className="text-vermilion-ink font-semibold">{String(plan.captain.web_name ?? plan.captain.id ?? "—")}</span>
        {plan.captain.proj != null ? ` ${Number(plan.captain.proj).toFixed(1)}` : ""} · VICE{" "}
        {String(plan.vice.web_name ?? plan.vice.id ?? "—")}
      </p>
      {plan.explanation ? (
        <div className="border-l border-rule pl-6 max-w-[62ch] mt-6">
          <p className="kicker mb-2">The agent&apos;s view</p>
          <p className="prose-body first-letter:font-[family-name:var(--font-fraunces)] first-letter:text-[3.2rem] first-letter:float-left first-letter:leading-[0.85] first-letter:pr-2 first-letter:font-bold first-letter:text-vermilion">
            {plan.explanation}
          </p>
          {plan.explanation_source === "llm" ? (
            <p className="caption mt-2">Written with AI from the agent&apos;s numbers.</p>
          ) : null}
        </div>
      ) : null}
      <div className="mt-6">
        {(plan.chips ?? []).map((c) => (
          <div
            key={c.chip}
            className={`border mb-4 ${c.recommend === "hold" ? "border-rule text-ink-faint" : "border-ink"}`}
          >
            {c.expires_soon ? <div className="bg-ochre-tint px-3 py-1.5 text-xs font-semibold">Expires soon</div> : null}
            <header className={`px-3 py-2 text-xs font-semibold tracking-widest uppercase ${c.recommend === "play_now" ? "bg-racing text-paper-bright" : ""}`}>
              {c.recommend === "play_now" ? `Play ${c.chip} now` : c.recommend.startsWith("consider") ? c.recommend.replaceAll("_", " ") : `Hold ${c.chip}`}
              {c.expected_gain ? ` · ${c.expected_gain >= 0 ? "+" : ""}${c.expected_gain}` : ""}
            </header>
          </div>
        ))}
      </div>
    </article>
  );
  if (locked) {
    return (
      <div className="relative">
        <div className="blur-[6px] pointer-events-none select-none">{inner}</div>
        <div className="absolute inset-0 grid place-items-center bg-[rgba(244,239,228,0.6)]">
          <div className="bg-paper-bright border border-ink shadow-[6px_6px_0_#161412] p-8 max-w-[420px] text-center">
            <p className="kicker">Members&apos; edition</p>
            <h2 className="mt-2">Your 5-week plan is one sign-in away</h2>
            <p className="prose-body mt-3">Sign in with Google to unlock your 5-week plan.</p>
            <a href="/login" className="btn btn-primary mt-4">
              Sign in with Google
            </a>
          </div>
        </div>
      </div>
    );
  }
  return inner;
}
