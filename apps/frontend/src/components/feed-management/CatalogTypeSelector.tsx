"use client";

import type { CatalogType } from "@/lib/types/feed-management";
import {
  Package,
  Car,
  Home,
  Building,
  Plane,
  Film,
} from "lucide-react";
import { cn } from "@/lib/utils";

type CatalogTypeOption = {
  type: CatalogType;
  label: string;
  description: string;
  icon: typeof Package;
  color: string;
  fieldsPreview: string;
};

const CATALOG_TYPES: CatalogTypeOption[] = [
  {
    type: "product",
    label: "Product",
    description: "Generic e-commerce product catalog",
    icon: Package,
    color: "text-indigo-600 dark:text-indigo-400",
    fieldsPreview: "Fields: title, price, description, image, availability, brand...",
  },
  {
    type: "vehicle",
    label: "Vehicle",
    description: "Auto dealership vehicle listings",
    icon: Car,
    color: "text-blue-600 dark:text-blue-400",
    fieldsPreview: "Fields: make, model, year, mileage, fuel_type, transmission...",
  },
  {
    type: "home_listing",
    label: "Home Listing",
    description: "Real estate property listings",
    icon: Home,
    color: "text-emerald-600 dark:text-emerald-400",
    fieldsPreview: "Fields: address, price, bedrooms, bathrooms, area, property_type...",
  },
  {
    type: "hotel",
    label: "Hotel",
    description: "Hospitality and hotel room listings",
    icon: Building,
    color: "text-amber-600 dark:text-amber-400",
    fieldsPreview: "Fields: name, price_per_night, star_rating, room_type, amenities...",
  },
  {
    type: "flight",
    label: "Flight",
    description: "Airline flight listings",
    icon: Plane,
    color: "text-sky-600 dark:text-sky-400",
    fieldsPreview: "Fields: origin, destination, departure, airline, cabin_class...",
  },
  {
    type: "media",
    label: "Media",
    description: "Entertainment and media content",
    icon: Film,
    color: "text-rose-600 dark:text-rose-400",
    fieldsPreview: "Fields: title, content_type, genre, release_date, rating, duration...",
  },
];

export function CatalogTypeSelector({
  selectedType,
  onSelect,
  disabled = false,
}: {
  selectedType: CatalogType | null;
  onSelect: (type: CatalogType) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <h3 className="mb-3 text-sm font-medium text-slate-500 dark:text-slate-400">Catalog Type</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CATALOG_TYPES.map((item) => {
          const isSelected = selectedType === item.type;
          const Icon = item.icon;
          return (
            <button
              key={item.type}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(item.type)}
              title={item.fieldsPreview}
              className={cn(
                "group relative flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition",
                disabled && "cursor-not-allowed opacity-50",
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
              <p className="mt-1 text-[10px] leading-tight text-slate-400 opacity-0 transition group-hover:opacity-100 dark:text-slate-500">
                {item.fieldsPreview}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
