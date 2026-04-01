"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { FeedSourceType } from "@/lib/types/feed-management";
import { SourceTypeSelector } from "@/components/feed-management/SourceTypeSelector";
import { FileSourceForm } from "@/components/feed-management/forms/FileSourceForm";
import { ShopifySourceForm } from "@/components/feed-management/forms/ShopifySourceForm";
import { GenericEcommerceForm } from "@/components/feed-management/forms/GenericEcommerceForm";
import { useFeedSources } from "@/lib/hooks/useFeedSources";

const FILE_TYPES: FeedSourceType[] = ["csv", "json", "xml", "google_sheets"];
const ECOMMERCE_TYPES: FeedSourceType[] = ["woocommerce", "magento", "bigcommerce"];

export default function NewSourcePage() {
  const router = useRouter();
  const { createSource, testConnection } = useFeedSources();
  const [selectedType, setSelectedType] = useState<FeedSourceType | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function handleCancel() {
    if (selectedType) {
      setSelectedType(null);
      setError("");
    } else {
      router.push("/agency/feed-management/sources");
    }
  }

  async function handleCreate(data: { name: string; source_type?: FeedSourceType; [key: string]: unknown }) {
    if (!selectedType) return;
    setBusy(true);
    setError("");
    try {
      await createSource({
        name: data.name as string,
        source_type: selectedType,
        url: (data.url ?? data.shop_url ?? data.store_url ?? "") as string,
        config: extractConfig(data),
      });
      router.push("/agency/feed-management/sources");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la crearea sursei.");
    } finally {
      setBusy(false);
    }
  }

  async function handleTestConnection(data: Record<string, string>): Promise<{ success: boolean; message: string }> {
    if (!selectedType) return { success: false, message: "Tipul sursei nu este selectat." };
    try {
      return await testConnection({
        source_type: selectedType,
        url: data.shop_url ?? data.store_url ?? "",
        config: data,
      });
    } catch {
      return { success: false, message: "Eroare la testarea conexiunii." };
    }
  }

  return (
    <>
      <div className="mb-6">
        <Link href="/agency/feed-management/sources" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
          <ArrowLeft className="h-4 w-4" />
          Înapoi la surse
        </Link>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Add New Source</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {selectedType ? "Configurează detaliile sursei de produse." : "Selectează tipul de sursă pe care vrei să o conectezi."}
        </p>
      </div>

      {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

      {selectedType === null ? (
        <>
          <SourceTypeSelector selectedType={selectedType} onSelect={setSelectedType} />
          <div className="mt-6">
            <button type="button" onClick={handleCancel} className="wm-btn-secondary">Anulează</button>
          </div>
        </>
      ) : (
        <div className="wm-card max-w-2xl p-6">
          {selectedType === "shopify" ? (
            <ShopifySourceForm
              onSubmit={(data) => void handleCreate({ ...data, source_type: "shopify" })}
              onTestConnection={handleTestConnection}
              onCancel={handleCancel}
              busy={busy}
            />
          ) : ECOMMERCE_TYPES.includes(selectedType) ? (
            <GenericEcommerceForm
              sourceType={selectedType}
              onSubmit={(data) => void handleCreate({ ...data, source_type: selectedType })}
              onTestConnection={handleTestConnection}
              onCancel={handleCancel}
              busy={busy}
            />
          ) : FILE_TYPES.includes(selectedType) ? (
            <FileSourceForm
              initialType={selectedType}
              onSubmit={(data) => void handleCreate({ name: data.name, url: data.url, source_type: data.file_type })}
              onCancel={handleCancel}
              busy={busy}
            />
          ) : null}
        </div>
      )}
    </>
  );
}

function extractConfig(data: Record<string, unknown>): Record<string, string> {
  const config: Record<string, string> = {};
  for (const [key, value] of Object.entries(data)) {
    if (key === "name" || key === "source_type" || key === "url") continue;
    if (typeof value === "string" && value.trim()) {
      config[key] = value.trim();
    }
  }
  return config;
}
