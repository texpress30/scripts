"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useFieldMapping, useCatalogSchema, useFieldMappingPreview } from "@/lib/hooks/useFieldMappings";
import { FieldMappingEditor } from "@/components/feed-management/FieldMappingEditor";
import { FieldMappingPreview } from "@/components/feed-management/FieldMappingPreview";
import { mockSourceFields } from "@/lib/mocks/fieldMappings";

const CATALOG_LABELS: Record<string, string> = {
  product: "Product",
  vehicle: "Vehicle",
  home_listing: "Home Listing",
  hotel: "Hotel",
  flight: "Flight",
  media: "Media",
};

export default function FieldMappingDetailPage() {
  const params = useParams<{ id: string }>();
  const mappingId = params.id;
  const { mapping, isLoading, error, updateRule, isUpdating } = useFieldMapping(mappingId);
  const { schema, isLoading: schemaLoading } = useCatalogSchema(mapping?.catalog_type ?? null);
  const { preview, isLoading: previewLoading, refresh } = useFieldMappingPreview(mappingId);

  if (isLoading || schemaLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error || !mapping) {
    return (
      <div className="py-8">
        <Link href="/agency/feed-management/field-mapping" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
          <ArrowLeft className="h-4 w-4" />
          Înapoi la mapări
        </Link>
        <p className="text-red-600">{error ?? "Maparea nu a fost găsită."}</p>
      </div>
    );
  }

  const catalogFields = schema?.fields ?? [];

  return (
    <>
      <Link href="/agency/feed-management/field-mapping" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
        <ArrowLeft className="h-4 w-4" />
        Înapoi la mapări
      </Link>

      <div className="mb-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Field Mapping — {mapping.source_name}
            </h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400">
                {CATALOG_LABELS[mapping.catalog_type] ?? mapping.catalog_type}
              </span>
              <span className="text-xs text-slate-400">
                {mapping.rules.length} rules &middot; Updated {new Date(mapping.updated_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Editor */}
      <div className="mb-6">
        <FieldMappingEditor
          catalogFields={catalogFields}
          sourceFields={mockSourceFields}
          rules={mapping.rules}
          onSaveRule={(rule) => void updateRule(rule)}
          isUpdating={isUpdating}
        />
      </div>

      {/* Preview */}
      <FieldMappingPreview
        preview={preview}
        isLoading={previewLoading}
        onRefresh={() => void refresh()}
      />
    </>
  );
}
