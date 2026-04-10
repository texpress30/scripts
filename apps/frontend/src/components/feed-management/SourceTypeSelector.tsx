"use client";

import type { FeedSourceType } from "@/lib/types/feed-management";
import {
  ShoppingBag,
  ShoppingCart,
  Store,
  Building2,
  Boxes,
  Package,
  Globe,
  Zap,
  Rocket,
  Truck,
  FileSpreadsheet,
  FileJson,
  FileCode,
  Sheet,
} from "lucide-react";
import { cn } from "@/lib/utils";

type SourceTypeOption = {
  type: FeedSourceType;
  label: string;
  description: string;
  icon: typeof ShoppingBag;
  color: string;
};

const ECOMMERCE_SOURCES: SourceTypeOption[] = [
  { type: "shopify", label: "Shopify", description: "Conectează-te la magazinul tău Shopify prin API", icon: ShoppingBag, color: "text-green-600 dark:text-green-400" },
  { type: "woocommerce", label: "WooCommerce", description: "Importă produse din WooCommerce via REST API", icon: ShoppingCart, color: "text-purple-600 dark:text-purple-400" },
  { type: "magento", label: "Magento", description: "Sincronizează catalogul din Magento 2", icon: Store, color: "text-orange-600 dark:text-orange-400" },
  { type: "bigcommerce", label: "BigCommerce", description: "Conectare la BigCommerce prin API", icon: Building2, color: "text-blue-600 dark:text-blue-400" },
  { type: "prestashop", label: "PrestaShop", description: "Importă produse din PrestaShop via Webservice API", icon: Boxes, color: "text-pink-600 dark:text-pink-400" },
  { type: "opencart", label: "OpenCart", description: "Conectare la OpenCart prin REST API", icon: Package, color: "text-cyan-600 dark:text-cyan-400" },
  { type: "shopware", label: "Shopware", description: "Sincronizează catalogul din Shopware 6", icon: Globe, color: "text-indigo-600 dark:text-indigo-400" },
  { type: "lightspeed", label: "Lightspeed", description: "Importă produse din Lightspeed eCom", icon: Zap, color: "text-yellow-600 dark:text-yellow-400" },
  { type: "volusion", label: "Volusion", description: "Conectare la Volusion prin API", icon: Truck, color: "text-red-600 dark:text-red-400" },
  { type: "cart_storefront", label: "Cart Storefront", description: "Importă produse din Cart.com", icon: Rocket, color: "text-fuchsia-600 dark:text-fuchsia-400" },
  { type: "gomag", label: "GoMag", description: "Importă produse din GoMag", icon: ShoppingBag, color: "text-lime-600 dark:text-lime-400" },
  { type: "contentspeed", label: "ContentSpeed", description: "Importă produse din ContentSpeed", icon: Zap, color: "text-sky-600 dark:text-sky-400" },
];

const FILE_SOURCES: SourceTypeOption[] = [
  { type: "csv", label: "CSV", description: "Importă produse dintr-un fișier CSV sau URL", icon: FileSpreadsheet, color: "text-emerald-600 dark:text-emerald-400" },
  { type: "json", label: "JSON", description: "Feed de produse în format JSON", icon: FileJson, color: "text-amber-600 dark:text-amber-400" },
  { type: "xml", label: "XML", description: "Feed de produse în format XML / Atom / RSS", icon: FileCode, color: "text-rose-600 dark:text-rose-400" },
  { type: "google_sheets", label: "Google Sheets", description: "Importă din Google Sheets public sau partajat", icon: Sheet, color: "text-teal-600 dark:text-teal-400" },
];

export function SourceTypeSelector({
  selectedType,
  onSelect,
}: {
  selectedType: FeedSourceType | null;
  onSelect: (type: FeedSourceType) => void;
}) {
  return (
    <div className="space-y-8">
      <SourceGroup title="E-commerce Platforms" items={ECOMMERCE_SOURCES} selectedType={selectedType} onSelect={onSelect} />
      <SourceGroup title="File Import" items={FILE_SOURCES} selectedType={selectedType} onSelect={onSelect} />
    </div>
  );
}

function SourceGroup({
  title,
  items,
  selectedType,
  onSelect,
}: {
  title: string;
  items: SourceTypeOption[];
  selectedType: FeedSourceType | null;
  onSelect: (type: FeedSourceType) => void;
}) {
  return (
    <div>
      <h3 className="mb-3 text-sm font-medium text-slate-500 dark:text-slate-400">{title}</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item) => {
          const isSelected = selectedType === item.type;
          const Icon = item.icon;
          return (
            <button
              key={item.type}
              type="button"
              onClick={() => onSelect(item.type)}
              className={cn(
                "flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition",
                isSelected
                  ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-500/20 dark:border-indigo-400 dark:bg-indigo-950/30 dark:ring-indigo-400/20"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600 dark:hover:bg-slate-800",
              )}
            >
              <Icon className={cn("h-6 w-6", item.color)} />
              <div>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{item.label}</p>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{item.description}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
