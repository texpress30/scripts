"use client";

import type { Product } from "@/lib/types/feed-management";
import { Package } from "lucide-react";

function formatPrice(price: number, currency: string): string {
  return `${price.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

export function ProductCard({
  product,
  onClick,
}: {
  product: Product;
  onClick: (product: Product) => void;
}) {
  const hasImage = product.images.length > 0;
  const inStock = product.inventory_quantity > 0;
  const onSale = product.compare_at_price !== null && product.compare_at_price > product.price;

  return (
    <button
      type="button"
      onClick={() => onClick(product)}
      className="wm-card group flex flex-col overflow-hidden text-left transition hover:shadow-md"
    >
      {/* Image */}
      <div className="relative aspect-square w-full overflow-hidden bg-slate-100 dark:bg-slate-800">
        {hasImage ? (
          <img
            src={product.images[0]}
            alt={product.title}
            className="h-full w-full object-cover transition group-hover:scale-105"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Package className="h-12 w-12 text-slate-300 dark:text-slate-600" />
          </div>
        )}
        {onSale ? (
          <span className="absolute left-2 top-2 rounded-full bg-red-500 px-2 py-0.5 text-xs font-medium text-white">Sale</span>
        ) : null}
      </div>

      {/* Info */}
      <div className="flex flex-1 flex-col p-3">
        <p className="line-clamp-2 text-sm font-medium text-slate-900 dark:text-slate-100">{product.title}</p>

        <div className="mt-1.5 flex items-baseline gap-2">
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            {formatPrice(product.price, product.currency)}
          </span>
          {onSale ? (
            <span className="text-xs text-slate-400 line-through">
              {formatPrice(product.compare_at_price!, product.currency)}
            </span>
          ) : null}
        </div>

        {product.category ? (
          <span className="mt-1.5 inline-flex w-fit rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400">
            {product.category}
          </span>
        ) : null}

        <div className="mt-auto flex items-center justify-between pt-2 text-xs text-slate-500 dark:text-slate-400">
          {product.sku ? <span>SKU: {product.sku}</span> : <span />}
          <span className={inStock ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}>
            {inStock ? `In stock (${product.inventory_quantity})` : "Out of stock"}
          </span>
        </div>
      </div>
    </button>
  );
}
