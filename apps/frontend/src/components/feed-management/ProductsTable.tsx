"use client";

import type { Product } from "@/lib/types/feed-management";
import { Package } from "lucide-react";

function formatPrice(price: number, currency: string): string {
  return `${price.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

export function ProductsTable({
  products,
  onClickProduct,
}: {
  products: Product[];
  onClickProduct: (product: Product) => void;
}) {
  if (products.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">
        Nu au fost gasite produse.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100 text-left text-slate-600 dark:bg-slate-800 dark:text-slate-400">
          <tr>
            <th className="px-4 py-3 w-12" />
            <th className="px-4 py-3">Title</th>
            <th className="px-4 py-3">SKU</th>
            <th className="px-4 py-3">Price</th>
            <th className="px-4 py-3">Category</th>
            <th className="px-4 py-3">Stock</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product) => {
            const inStock = product.inventory_quantity > 0;
            const onSale = product.compare_at_price !== null && product.compare_at_price > product.price;
            return (
              <tr
                key={product.id}
                onClick={() => onClickProduct(product)}
                className="cursor-pointer border-t border-slate-100 transition hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50"
              >
                <td className="px-4 py-3">
                  <div className="h-10 w-10 overflow-hidden rounded bg-slate-100 dark:bg-slate-800">
                    {product.images.length > 0 ? (
                      <img src={product.images[0]} alt="" className="h-full w-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <Package className="h-4 w-4 text-slate-400" />
                      </div>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="font-medium text-slate-900 dark:text-slate-100">{product.title}</span>
                </td>
                <td className="px-4 py-3 text-slate-500 dark:text-slate-400">{product.sku || "\u2014"}</td>
                <td className="px-4 py-3">
                  <span className="font-medium text-slate-900 dark:text-slate-100">{formatPrice(product.price, product.currency)}</span>
                  {onSale ? (
                    <span className="ml-1 text-xs text-slate-400 line-through">{formatPrice(product.compare_at_price!, product.currency)}</span>
                  ) : null}
                </td>
                <td className="px-4 py-3">
                  {product.category ? (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400">{product.category}</span>
                  ) : <span className="text-slate-400">&mdash;</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium ${inStock ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                    {inStock ? `${product.inventory_quantity} in stock` : "Out of stock"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
