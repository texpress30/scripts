"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { FeedSourceType, CatalogType } from "@/lib/types/feed-management";
import { SourceTypeSelector } from "@/components/feed-management/SourceTypeSelector";
import { CatalogTypeSelector } from "@/components/feed-management/CatalogTypeSelector";
import { FileSourceForm } from "@/components/feed-management/forms/FileSourceForm";
import { ShopifySourceForm } from "@/components/feed-management/forms/ShopifySourceForm";
import { GenericEcommerceForm } from "@/components/feed-management/forms/GenericEcommerceForm";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";

const FILE_TYPES: FeedSourceType[] = ["csv", "json", "xml", "google_sheets"];
const ECOMMERCE_TYPES: FeedSourceType[] = ["woocommerce", "magento", "bigcommerce"];

type Step = "source_type" | "catalog_type" | "configure";

export default function NewSourcePage() {
  const router = useRouter();
  const { selectedId, selectedClient, isLoading: clientsLoading } = useFeedManagement();
  const { createSource, testConnection } = useFeedSources(selectedId);
  const [step, setStep] = useState<Step>("source_type");
  const [selectedType, setSelectedType] = useState<FeedSourceType | null>(null);
  const [selectedCatalog, setSelectedCatalog] = useState<CatalogType>("product");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function handleSelectSourceType(type: FeedSourceType) {
    setSelectedType(type);
    setStep("catalog_type");
    setError("");
  }

  function handleSelectCatalogType(type: CatalogType) {
    setSelectedCatalog(type);
  }

  function handleCatalogContinue() {
    setStep("configure");
    setError("");
  }

  function handleBack() {
    if (step === "configure") {
      setStep("catalog_type");
      setError("");
    } else if (step === "catalog_type") {
      setSelectedType(null);
      setStep("source_type");
      setError("");
    } else {
      router.push("/agency/feed-management/sources");
    }
  }

  async function handleCreate(data: { name: string; source_type?: FeedSourceType; [key: string]: unknown }) {
    if (!selectedType) return;
    if (!selectedId) {
      setError("Selectează un client înainte de a crea sursa.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createSource({
        name: data.name as string,
        source_type: selectedType,
        catalog_type: selectedCatalog,
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
    } catch (err) {
      return { success: false, message: err instanceof Error ? err.message : "Eroare la testarea conexiunii." };
    }
  }

  const stepNumber = step === "source_type" ? 1 : step === "catalog_type" ? 2 : 3;
  const stepLabels: Record<Step, string> = {
    source_type: "Selectează tipul de sursă pe care vrei să o conectezi.",
    catalog_type: "Selectează tipul de catalog pentru datele importate.",
    configure: "Configurează detaliile sursei de produse.",
  };

  return (
    <>
      <div className="mb-6">
        <Link href="/agency/feed-management/sources" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
          <ArrowLeft className="h-4 w-4" />
          Înapoi la surse
        </Link>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Add New Source</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{stepLabels[step]}</p>

        {/* Step indicator */}
        <div className="mt-4 flex items-center gap-2">
          {[1, 2, 3].map((n) => (
            <div key={n} className="flex items-center gap-2">
              <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition ${n <= stepNumber ? "bg-indigo-600 text-white" : "bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-400"}`}>
                {n}
              </div>
              <span className={`text-xs font-medium ${n <= stepNumber ? "text-slate-900 dark:text-slate-100" : "text-slate-400 dark:text-slate-500"}`}>
                {n === 1 ? "Source Type" : n === 2 ? "Catalog Type" : "Configure"}
              </span>
              {n < 3 && <div className={`h-px w-8 ${n < stepNumber ? "bg-indigo-600" : "bg-slate-200 dark:bg-slate-700"}`} />}
            </div>
          ))}
        </div>
      </div>

      {selectedClient && (
        <p className="mb-4 text-xs text-slate-400">Sursa va fi creata pentru clientul <strong className="text-slate-600 dark:text-slate-300">{selectedClient.name}</strong>.</p>
      )}

      {!selectedId && !clientsLoading ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-400">
          Selecteaza un client din header-ul de mai sus pentru a continua.
        </div>
      ) : (
        <>
          {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

          {step === "source_type" && (
            <>
              <SourceTypeSelector selectedType={selectedType} onSelect={handleSelectSourceType} />
              <div className="mt-6">
                <button type="button" onClick={handleBack} className="wm-btn-secondary">Anulează</button>
              </div>
            </>
          )}

          {step === "catalog_type" && (
            <>
              <CatalogTypeSelector selectedType={selectedCatalog} onSelect={handleSelectCatalogType} />
              <div className="mt-6 flex gap-3">
                <button type="button" onClick={handleBack} className="wm-btn-secondary">Înapoi</button>
                <button type="button" onClick={handleCatalogContinue} className="wm-btn-primary">Continuă</button>
              </div>
            </>
          )}

          {step === "configure" && selectedType !== null && (
            <div className="wm-card max-w-2xl p-6">
              {selectedType === "shopify" ? (
                <ShopifySourceForm
                  onSubmit={(data) => void handleCreate({ ...data, source_type: "shopify" })}
                  onTestConnection={handleTestConnection}
                  onCancel={handleBack}
                  busy={busy}
                />
              ) : ECOMMERCE_TYPES.includes(selectedType) ? (
                <GenericEcommerceForm
                  sourceType={selectedType}
                  onSubmit={(data) => void handleCreate({ ...data, source_type: selectedType })}
                  onTestConnection={handleTestConnection}
                  onCancel={handleBack}
                  busy={busy}
                />
              ) : FILE_TYPES.includes(selectedType) ? (
                <FileSourceForm
                  initialType={selectedType}
                  onSubmit={(data) => void handleCreate({ name: data.name, url: data.url, source_type: data.file_type })}
                  onCancel={handleBack}
                  busy={busy}
                />
              ) : null}
            </div>
          )}
        </>
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
