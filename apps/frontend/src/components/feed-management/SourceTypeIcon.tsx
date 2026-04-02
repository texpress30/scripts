import {
  ShoppingBag,
  ShoppingCart,
  Store,
  Building2,
  FileSpreadsheet,
  FileJson,
  FileCode,
  Sheet,
} from "lucide-react";
import type { FeedSourceType } from "@/lib/types/feed-management";

const SOURCE_TYPE_CONFIG: Record<FeedSourceType, { icon: typeof ShoppingBag; label: string; color: string }> = {
  shopify: { icon: ShoppingBag, label: "Shopify", color: "text-green-600 dark:text-green-400" },
  woocommerce: { icon: ShoppingCart, label: "WooCommerce", color: "text-purple-600 dark:text-purple-400" },
  magento: { icon: Store, label: "Magento", color: "text-orange-600 dark:text-orange-400" },
  bigcommerce: { icon: Building2, label: "BigCommerce", color: "text-blue-600 dark:text-blue-400" },
  csv: { icon: FileSpreadsheet, label: "CSV", color: "text-emerald-600 dark:text-emerald-400" },
  json: { icon: FileJson, label: "JSON", color: "text-amber-600 dark:text-amber-400" },
  xml: { icon: FileCode, label: "XML", color: "text-rose-600 dark:text-rose-400" },
  google_sheets: { icon: Sheet, label: "Google Sheets", color: "text-teal-600 dark:text-teal-400" },
};

export function SourceTypeIcon({
  type,
  showLabel = false,
  className = "",
}: {
  type: FeedSourceType;
  showLabel?: boolean;
  className?: string;
}) {
  const config = SOURCE_TYPE_CONFIG[type] ?? SOURCE_TYPE_CONFIG.csv;
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <Icon className={`h-4 w-4 ${config.color}`} />
      {showLabel ? <span className="text-sm text-slate-700 dark:text-slate-300">{config.label}</span> : null}
    </span>
  );
}
