"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type StorageUsageItem = {
  id: number;
  name: string;
  address: string;
  media_storage_bytes: number;
};

type StorageUsageResponse = {
  items: StorageUsageItem[];
  total: number;
  page: number;
  page_size: number;
};

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

function formatStorage(bytes: number) {
  const normalized = Number.isFinite(bytes) ? Math.max(0, bytes) : 0;
  const mb = normalized / (1024 * 1024);
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${mb.toFixed(0)} MB`;
}

export default function SettingsStoragePage() {
  const [items, setItems] = useState<StorageUsageItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [refreshTick, setRefreshTick] = useState(0);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

  useEffect(() => {
    let ignore = false;
    async function loadUsage() {
      setLoading(true);
      setErrorMessage("");
      try {
        const params = new URLSearchParams({
          search,
          page: String(page),
          page_size: String(pageSize),
        });
        const payload = await apiRequest<StorageUsageResponse>(`/storage/media-usage?${params.toString()}`);
        if (ignore) return;
        setItems(payload.items);
        setTotal(payload.total);
      } catch (err) {
        if (ignore) return;
        setItems([]);
        setTotal(0);
        setErrorMessage(err instanceof Error ? err.message : "Nu am putut încărca utilizarea stocării.");
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void loadUsage();
    return () => {
      ignore = true;
    };
  }, [search, page, pageSize, refreshTick]);

  // Keep the totals fresh: refetch once every 24h while the tab is visible
  // and whenever the window regains focus, so new uploads in a sub-account's
  // Media Storage surface here without a manual reload.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const triggerRefresh = () => setRefreshTick((prev) => prev + 1);
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") triggerRefresh();
    }, 24 * 60 * 60 * 1000);
    const onFocus = () => triggerRefresh();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  return (
    <ProtectedPage>
      <AppShell title="Utilizare Stocare Media">
        <main className="space-y-4 p-6">
          <h1 className="text-2xl font-semibold text-slate-900">Utilizare Stocare Media</h1>

          {errorMessage ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</div> : null}

          <section className="wm-card p-4 shadow-sm">
            <header className="flex flex-col gap-3 border-b border-slate-100 pb-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-semibold text-slate-900">Utilizare per Sub-cont</h2>
                  <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">{total} Sub-conturi</span>
                </div>
                <p className="mt-1 text-sm text-slate-500">Spațiul de stocare media utilizat de toate sub-conturile</p>
              </div>

              <label className="relative block w-full max-w-md">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  className="wm-input pl-9"
                  placeholder="Caută după numele sub-contului"
                  value={search}
                  onChange={(e) => {
                    setPage(1);
                    setSearch(e.target.value);
                  }}
                />
              </label>
            </header>

            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Nume</th>
                    <th className="px-3 py-2">Spațiu Utilizat</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={2} className="px-3 py-8 text-center text-slate-500">Se încarcă utilizarea stocării...</td>
                    </tr>
                  ) : items.length === 0 ? (
                    <tr>
                      <td colSpan={2} className="px-3 py-8 text-center text-slate-500">Nu există sub-conturi pentru filtrul curent.</td>
                    </tr>
                  ) : (
                    items.map((item) => (
                      <tr key={item.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 align-top">
                          <p className="font-semibold text-slate-900">{item.name}</p>
                          <p className="text-xs text-slate-500">{item.address}</p>
                        </td>
                        <td className="px-3 py-2 align-top text-slate-800">{formatStorage(item.media_storage_bytes)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <footer className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3 text-sm text-slate-600 md:flex-row md:items-center md:justify-end">
              <select
                className="wm-input h-9 w-auto"
                value={pageSize}
                onChange={(e) => {
                  setPage(1);
                  setPageSize(Number(e.target.value));
                }}
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>{size} / pagină</option>
                ))}
              </select>
              <span>Pagina {page} din {totalPages}</span>
              <div className="flex items-center gap-2">
                <button className="wm-btn-secondary inline-flex items-center gap-1" type="button" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
                  <ChevronLeft className="h-4 w-4" /> Înapoi
                </button>
                <button className="wm-btn-secondary inline-flex items-center gap-1" type="button" disabled={page >= totalPages} onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}>
                  Înainte <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </footer>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
