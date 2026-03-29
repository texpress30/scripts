export default function AgencyDashboardLoading() {
  const pulse = "animate-pulse rounded bg-slate-200";

  return (
    <div className="p-6">
      <div className="mb-4 flex justify-between">
        <div className={`${pulse} h-7 w-48`} />
        <div className={`${pulse} h-9 w-56`} />
      </div>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-4 xl:grid-cols-7">
        {Array.from({ length: 7 }).map((_, i) => (
          <article key={i} className="wm-card p-4">
            <div className={`${pulse} mb-3 h-3 w-20`} />
            <div className={`${pulse} h-7 w-24`} />
          </article>
        ))}
      </section>

      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <article className="wm-card p-4">
          <div className={`${pulse} mb-4 h-4 w-36`} />
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between py-2">
              <div className={`${pulse} h-3 w-32`} />
              <div className={`${pulse} h-3 w-16`} />
            </div>
          ))}
        </article>
        <article className="wm-card p-4">
          <div className={`${pulse} mb-4 h-4 w-40`} />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between py-2">
              <div className={`${pulse} h-3 w-28`} />
              <div className={`${pulse} h-3 w-20`} />
            </div>
          ))}
        </article>
      </section>
    </div>
  );
}
