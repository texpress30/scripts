"use client";

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, LayoutGrid, List, Loader2, ShoppingBag, Clock, FolderOpen } from "lucide-react";
import { useFeedSource } from "@/lib/hooks/useFeedSources";
import { useFeedProducts, useFeedProductStats, useFeedProductCategories } from "@/lib/hooks/useFeedProducts";
import { ProductCard } from "@/components/feed-management/ProductCard";
import { ProductsTable } from "@/components/feed-management/ProductsTable";
import { ProductDetailModal } from "@/components/feed-management/ProductDetailModal";
import { ProductsSearchBar } from "@/components/feed-management/ProductsSearchBar";
import { ProductsPagination } from "@/components/feed-management/ProductsPagination";
import type { Product } from "@/lib/types/feed-management";

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function SourceProductsPage() {
  const params = useParams<{ id: string }>();
  const sourceId = Number(params.id);

  const { source } = useFeedSource(sourceId);
  const { stats } = useFeedProductStats(sourceId);
  const { categories } = useFeedProductCategories(sourceId);

  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(25);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  const { products, total, isLoading, error } = useFeedProducts(sourceId, { page, limit, search, category });

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleCategoryChange = useCallback((value: string) => {
    setCategory(value);
    setPage(1);
  }, []);

  const handleLimitChange = useCallback((value: number) => {
    setLimit(value);
    setPage(1);
  }, []);

  const categoriesCount = stats ? Object.keys(stats.by_category).length : 0;

  return (
    <>
      {/* Breadcrumb */}
      <div className="mb-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <Link href="/agency/feed-management/sources" className="hover:text-slate-700 dark:hover:text-slate-300">Sources</Link>
        <span>/</span>
        <Link href={`/agency/feed-management/sources/${sourceId}`} className="hover:text-slate-700 dark:hover:text-slate-300">
          {source?.name ?? `Source #${sourceId}`}
        </Link>
        <span>/</span>
        <span className="text-slate-900 dark:text-slate-100">Products</span>
      </div>

      {/* Header */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Products {source ? `\u2014 ${source.name}` : ""}
          </h1>
        </div>
        <Link href={`/agency/feed-management/sources/${sourceId}`} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
          <ArrowLeft className="h-4 w-4" /> Back to source
        </Link>
      </div>

      {/* Stats bar */}
      {stats ? (
        <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="wm-card flex items-center gap-3 p-4">
            <div className="rounded-lg bg-indigo-50 p-2 dark:bg-indigo-900/30">
              <ShoppingBag className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400">Total Products</p>
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{stats.total.toLocaleString()}</p>
            </div>
          </div>
          <div className="wm-card flex items-center gap-3 p-4">
            <div className="rounded-lg bg-emerald-50 p-2 dark:bg-emerald-900/30">
              <FolderOpen className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400">Categories</p>
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{categoriesCount}</p>
            </div>
          </div>
          <div className="wm-card flex items-center gap-3 p-4">
            <div className="rounded-lg bg-amber-50 p-2 dark:bg-amber-900/30">
              <Clock className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400">Last Sync</p>
              <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{formatDate(stats.last_sync)}</p>
            </div>
          </div>
        </div>
      ) : null}

      {/* Search, filter, view toggle */}
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex-1">
          <ProductsSearchBar
            search={search}
            onSearchChange={handleSearchChange}
            category={category}
            onCategoryChange={handleCategoryChange}
            categories={categories}
            totalResults={total}
          />
        </div>
        <div className="flex rounded-lg border border-slate-200 dark:border-slate-700">
          <button
            type="button"
            onClick={() => setViewMode("grid")}
            className={`rounded-l-lg px-3 py-2 ${viewMode === "grid" ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400" : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800"}`}
            aria-label="Grid view"
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setViewMode("table")}
            className={`rounded-r-lg px-3 py-2 ${viewMode === "table" ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400" : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800"}`}
            aria-label="Table view"
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {error ? <p className="mb-4 text-red-600">{error}</p> : null}

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : products.length === 0 ? (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <ShoppingBag className="mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
          <h2 className="text-lg font-medium text-slate-700 dark:text-slate-300">
            {search || category ? "Nu au fost gasite produse" : "Nu exista produse importate"}
          </h2>
          <p className="mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">
            {search || category
              ? "Incearca sa modifici filtrele sau termenul de cautare."
              : "Ruleaza o sincronizare pentru a importa produse din aceasta sursa."}
          </p>
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} onClick={setSelectedProduct} />
          ))}
        </div>
      ) : (
        <div className="wm-card overflow-hidden">
          <ProductsTable products={products} onClickProduct={setSelectedProduct} />
        </div>
      )}

      {/* Pagination */}
      {total > 0 ? (
        <ProductsPagination
          page={page}
          limit={limit}
          total={total}
          onPageChange={setPage}
          onLimitChange={handleLimitChange}
        />
      ) : null}

      {/* Product detail modal */}
      {selectedProduct ? (
        <ProductDetailModal product={selectedProduct} onClose={() => setSelectedProduct(null)} />
      ) : null}
    </>
  );
}
