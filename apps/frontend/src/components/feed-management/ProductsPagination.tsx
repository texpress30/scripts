"use client";

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

export function ProductsPagination({
  page,
  limit,
  total,
  onPageChange,
  onLimitChange,
}: {
  page: number;
  limit: number;
  total: number;
  onPageChange: (page: number) => void;
  onLimitChange: (limit: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const from = total === 0 ? 0 : (page - 1) * limit + 1;
  const to = Math.min(page * limit, total);

  return (
    <section className="mt-4 flex flex-col items-center justify-between gap-3 text-sm text-slate-600 dark:text-slate-400 sm:flex-row">
      <p>
        {total === 0
          ? "Niciun produs"
          : `Afisare ${from}-${to} din ${total.toLocaleString()}`}
      </p>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span>Pe pagina</span>
          <select
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          >
            {PAGE_SIZE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="rounded border border-slate-300 px-3 py-1 disabled:opacity-50 dark:border-slate-700"
          >
            Anterior
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="rounded border border-slate-300 px-3 py-1 disabled:opacity-50 dark:border-slate-700"
          >
            Urmator
          </button>
        </div>
      </div>
    </section>
  );
}
