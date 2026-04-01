"use client";

import { useState } from "react";
import { X, ExternalLink, Package, ChevronLeft, ChevronRight } from "lucide-react";
import type { Product } from "@/lib/types/feed-management";

function formatPrice(price: number, currency: string): string {
  return `${price.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

export function ProductDetailModal({
  product,
  onClose,
}: {
  product: Product;
  onClose: () => void;
}) {
  const [imageIdx, setImageIdx] = useState(0);
  const hasImages = product.images.length > 0;
  const inStock = product.inventory_quantity > 0;
  const onSale = product.compare_at_price !== null && product.compare_at_price > product.price;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 mx-4 max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white shadow-xl dark:bg-slate-900">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{product.title}</h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-6 p-6 md:grid-cols-2">
          {/* Image gallery */}
          <div>
            <div className="relative aspect-square overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
              {hasImages ? (
                <>
                  <img src={product.images[imageIdx]} alt={product.title} className="h-full w-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                  {product.images.length > 1 ? (
                    <>
                      <button type="button" onClick={() => setImageIdx((i) => (i - 1 + product.images.length) % product.images.length)} className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-white/80 p-1.5 shadow hover:bg-white dark:bg-slate-900/80 dark:hover:bg-slate-900">
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      <button type="button" onClick={() => setImageIdx((i) => (i + 1) % product.images.length)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-white/80 p-1.5 shadow hover:bg-white dark:bg-slate-900/80 dark:hover:bg-slate-900">
                        <ChevronRight className="h-4 w-4" />
                      </button>
                      <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-1">
                        {product.images.map((_, i) => (
                          <span key={i} className={`h-1.5 w-1.5 rounded-full ${i === imageIdx ? "bg-indigo-600" : "bg-white/60"}`} />
                        ))}
                      </div>
                    </>
                  ) : null}
                </>
              ) : (
                <div className="flex h-full w-full items-center justify-center">
                  <Package className="h-16 w-16 text-slate-300 dark:text-slate-600" />
                </div>
              )}
            </div>
          </div>

          {/* Details */}
          <div className="space-y-4">
            <div>
              <div className="flex items-baseline gap-3">
                <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {formatPrice(product.price, product.currency)}
                </span>
                {onSale ? (
                  <span className="text-base text-slate-400 line-through">
                    {formatPrice(product.compare_at_price!, product.currency)}
                  </span>
                ) : null}
              </div>
              {onSale ? (
                <span className="mt-1 inline-block rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                  {Math.round((1 - product.price / product.compare_at_price!) * 100)}% off
                </span>
              ) : null}
            </div>

            {product.description ? (
              <p className="text-sm text-slate-600 dark:text-slate-400">{product.description}</p>
            ) : null}

            <dl className="space-y-2 text-sm">
              {product.sku ? <DetailItem label="SKU">{product.sku}</DetailItem> : null}
              {product.category ? <DetailItem label="Category">{product.category}</DetailItem> : null}
              <DetailItem label="Stock">
                <span className={inStock ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}>
                  {inStock ? `${product.inventory_quantity} in stock` : "Out of stock"}
                </span>
              </DetailItem>
              {product.tags.length > 0 ? (
                <DetailItem label="Tags">
                  <div className="flex flex-wrap gap-1">
                    {product.tags.map((tag) => (
                      <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400">{tag}</span>
                    ))}
                  </div>
                </DetailItem>
              ) : null}
              {product.variants.length > 0 ? (
                <DetailItem label={`Variants (${product.variants.length})`}>
                  <div className="mt-1 space-y-1">
                    {product.variants.map((v) => (
                      <div key={v.sku} className="flex items-center justify-between rounded bg-slate-50 px-2 py-1 text-xs dark:bg-slate-800">
                        <span className="font-medium text-slate-700 dark:text-slate-300">{v.title}</span>
                        <span className="text-slate-500">{v.sku} &middot; {v.inventory_quantity} in stock</span>
                      </div>
                    ))}
                  </div>
                </DetailItem>
              ) : null}
            </dl>

            {product.url ? (
              <a href={product.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-sm text-indigo-600 hover:underline dark:text-indigo-400">
                <ExternalLink className="h-3.5 w-3.5" />
                View original product
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-slate-700 dark:text-slate-300">{children}</dd>
    </div>
  );
}
