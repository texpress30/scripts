"use client";

type Platform = { spend: number; conversions: number; roas?: number };

type DashboardTotals = {
  spend: number;
  conversions: number;
  roas: number;
};

export function NewDashboardOverview({
  totals,
  google,
  meta
}: {
  totals: DashboardTotals;
  google: Platform;
  meta: Platform;
}) {
  const topPlatform = google.spend >= meta.spend ? "Google Ads" : "Meta Ads";

  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <article className="wm-card p-4 lg:col-span-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Performance snapshot</h3>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Stat title="Spend total" value={`$${totals.spend.toLocaleString()}`} />
          <Stat title="Conversii" value={totals.conversions.toLocaleString()} />
          <Stat title="ROAS mediu" value={totals.roas.toFixed(2)} />
        </div>
      </article>

      <article className="wm-card p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Recomandare rapidă</h3>
        <p className="mt-3 text-sm text-slate-700">
          Canal dominant: <span className="font-semibold text-slate-900">{topPlatform}</span>.
        </p>
        <p className="mt-2 text-sm text-slate-600">
          Verifică bugetele și mută incremental spend către canalul cu ROAS mai bun.
        </p>
      </article>
    </section>
  );
}

function Stat({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
