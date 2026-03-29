export default function AgencyAccountsLoading() {
  const pulse = "animate-pulse rounded bg-slate-200";

  return (
    <div className="p-6">
      <div className="mb-6">
        <div className={`${pulse} h-7 w-48`} />
      </div>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="wm-card p-4">
            <div className={`${pulse} mb-2 h-4 w-24`} />
            <div className={`${pulse} h-6 w-12`} />
          </div>
        ))}
      </section>

      <section className="mt-6">
        <div className="wm-card p-4">
          <div className="mb-4 flex items-center justify-between">
            <div className={`${pulse} h-4 w-32`} />
            <div className="flex gap-2">
              <div className={`${pulse} h-8 w-24`} />
              <div className={`${pulse} h-8 w-24`} />
            </div>
          </div>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between border-b border-slate-100 py-3">
              <div className="flex items-center gap-3">
                <div className={`${pulse} h-4 w-4 rounded-sm`} />
                <div className={`${pulse} h-4 w-36`} />
              </div>
              <div className="flex items-center gap-4">
                <div className={`${pulse} h-3 w-20`} />
                <div className={`${pulse} h-3 w-16`} />
                <div className={`${pulse} h-6 w-16 rounded-full`} />
              </div>
            </div>
          ))}
          <div className="mt-3 flex items-center justify-between">
            <div className={`${pulse} h-3 w-32`} />
            <div className="flex gap-2">
              <div className={`${pulse} h-8 w-20`} />
              <div className={`${pulse} h-8 w-20`} />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
