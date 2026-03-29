export default function SubDashboardLoading() {
  const pulse = "animate-pulse rounded bg-slate-200";

  return (
    <div className="p-6">
      <div className="mb-4 flex justify-between">
        <div className="flex gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className={`${pulse} h-8 w-24`} />
          ))}
        </div>
        <div className={`${pulse} h-9 w-56`} />
      </div>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="wm-card p-4">
            <div className={`${pulse} mb-3 h-3 w-16`} />
            <div className={`${pulse} h-7 w-20`} />
          </div>
        ))}
      </section>

      <section className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="wm-card p-4">
            <div className={`${pulse} mb-3 h-4 w-40`} />
            <div className={`${pulse} h-48 w-full rounded-lg`} />
          </div>
        ))}
      </section>

      <section className="mt-6">
        <div className="wm-card overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <div className="grid grid-cols-7 gap-4">
              {Array.from({ length: 7 }).map((_, i) => (
                <div key={i} className={`${pulse} h-3 w-16`} />
              ))}
            </div>
          </div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="border-b border-slate-100 px-4 py-3">
              <div className="grid grid-cols-7 gap-4">
                {Array.from({ length: 7 }).map((_, j) => (
                  <div key={j} className={`${pulse} h-3 ${j === 0 ? "w-20" : "w-14"}`} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
