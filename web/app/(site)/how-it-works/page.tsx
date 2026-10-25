export default function HowItWorksPage() {
  return (
    <article className="prose-body max-w-[62ch]">
      <h1>How it works</h1>
      <h2 className="mt-10">§ 1 · Import</h2>
      <p className="mt-3">
        FPLBud looks up a public FPL team ID. It never asks for your FPL password. Free transfers and selling prices
        are estimated from the public history, and you can override them.
      </p>
      <h2 className="mt-10">§ 2 · Score</h2>
      <p className="mt-3">
        Each player is marked on form, fixture difficulty, home advantage, expected stats, value and minutes
        security. Transfer trend is optional. Scores are percentiles within position, then mixed with your weights.
      </p>
      <div className="border border-rule p-4 my-4 font-[family-name:var(--font-instrument)] nums">
        S = Σ wᵢ × scoreᵢ / Σ wᵢ
        <br />
        proj = n_fixtures × availability × (1 + 6 × S)
      </div>
      <h2 className="mt-10">§ 3 · Plan</h2>
      <p className="mt-3">
        A small integer programme picks this week&apos;s transfers, the XI, the bench and the captain. Hits are only
        taken when the extra projected points clear a margin: 6.0 over one week, 5.0 over three, 4.5 over five.
      </p>
      <h2 className="mt-10">§ 4 · Chips</h2>
      <p className="mt-3">
        Bench Boost if the bench is worth 12 or more. Triple Captain if the captain projects 10 or more. Free Hit if a
        fresh XI gains 12. Wildcard (five-week view) if a full rebuild gains 20.
      </p>
    </article>
  );
}
