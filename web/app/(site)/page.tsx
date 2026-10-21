import { GoogleButton } from "@/components/programme/GoogleButton";
import { LandingLookup } from "@/components/programme/LandingLookup";

export default function LandingPage() {
  return (
    <>
      <p className="kicker">The FPL tactics column</p>
      <h1 className="masthead-type mt-2">
        FPL<em className="italic font-bold">Bud</em>
        <span className="text-vermilion">.</span>
      </h1>
      <p className="prose-body text-xl mt-4 max-w-[40ch]">
        Paste your team ID for a squad score. Sign in for transfers, expected points and who is running hot or cold.
      </p>
      <div className="double-rule mt-8" />
      <div className="broadsheet">
        <div>
          <LandingLookup />
        </div>
        <div className="col-rule" />
        <div>
          <p className="kicker">Members&apos; edition</p>
          <h2 className="mt-2">See the rest of the report</h2>
          <p className="prose-body mt-3">
            Sign in to unlock expected points, transfer suggestions, and your performing and underperforming players.
          </p>
          <div className="mt-4 max-w-xs">
            <GoogleButton />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1px_1fr_1px_1fr] gap-6 mt-12">
        {[
          ["1", "Import", "Drop in your public team ID. No FPL password. Ever."],
          ["2", "Score", "Your starting XI, marked on form, fixtures, home games and expected stats."],
          ["3", "Unlock", "Sign in for transfers, expected points, and who in the squad is performing."],
        ].flatMap(([n, t, d], index) => {
          const step = (
            <article key={n}>
              <p className="kicker">{t}</p>
              <span className="stat-xl block my-2">{n}</span>
              <p className="prose-body">{d}</p>
            </article>
          );
          if (index === 0) return [step];
          return [<div key={`${n}-rule`} className="col-rule" aria-hidden="true" />, step];
        })}
      </div>
    </>
  );
}
