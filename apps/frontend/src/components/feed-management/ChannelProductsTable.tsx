"use client";

import { ExternalLink } from "lucide-react";
import type { ColumnDef } from "@/lib/hooks/useChannelProducts";
import { ProductImageCell } from "./ProductImageCell";

type Props = {
  products: Record<string, unknown>[];
  columns: ColumnDef[];
  visibleColumns: Set<string>;
};

function CellValue({ value, type }: { value: unknown; type: string }) {
  if (value == null || value === "") {
    return <span className="text-slate-300 dark:text-slate-600">&mdash;</span>;
  }

  if (type === "image") {
    return <ProductImageCell src={value} />;
  }

  if (type === "url") {
    const url = String(value);
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex max-w-[250px] items-center gap-1 text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
        title={url}
      >
        <span className="truncate text-xs">{url}</span>
        <ExternalLink className="h-3 w-3 shrink-0" />
      </a>
    );
  }

  if (type === "price") {
    return <span className="font-mono text-xs">{String(value)}</span>;
  }

  const text = String(value);
  return (
    <span className="line-clamp-3 text-xs" title={text}>
      {text}
    </span>
  );
}

export function ChannelProductsTable({ products, columns, visibleColumns }: Props) {
  const cols = columns.filter((c) => visibleColumns.has(c.key));

  if (products.length === 0) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-slate-400 dark:text-slate-500">No products match your criteria.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50">
            {cols.map((col) => (
              <th
                key={col.key}
                className="whitespace-nowrap px-4 py-2.5 text-xs font-semibold text-slate-600 dark:text-slate-400"
              >
                <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-indigo-500" />
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
          {products.map((product, idx) => (
            <tr
              key={idx}
              className="hover:bg-slate-50 dark:hover:bg-slate-800/30"
            >
              {cols.map((col) => (
                <td
                  key={col.key}
                  className="max-w-[280px] px-4 py-3 align-top text-slate-700 dark:text-slate-300"
                >
                  <CellValue value={product[col.key]} type={col.type} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
