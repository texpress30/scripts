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
import {
  ShopifyClaimForm,
  type ShopifyClaimFormData,
} from "@/components/feed-management/forms/ShopifyClaimForm";
import { GenericEcommerceForm } from "@/components/feed-management/forms/GenericEcommerceForm";
import {
  MagentoSourceForm,
  type MagentoConnectFormData,
  type MagentoTestConnectionResult,
} from "@/components/feed-management/forms/MagentoSourceForm";
import {
  BigCommerceClaimForm,
  type BigCommerceClaimFormData,
} from "@/components/feed-management/forms/BigCommerceClaimForm";
import {
  GenericApiKeySourceForm,
  type GenericApiKeyFormData,
} from "@/components/feed-management/forms/GenericApiKeySourceForm";
import {
  LightspeedSourceForm,
  type LightspeedFormData,
} from "@/components/feed-management/forms/LightspeedSourceForm";
import {
  ShopwareSourceForm,
  type ShopwareFormData,
} from "@/components/feed-management/forms/ShopwareSourceForm";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import {
  createMagentoSourceApi,
  testMagentoConnectionBeforeSave,
} from "@/lib/hooks/useMagentoSource";
import { claimBigCommerceStore } from "@/lib/hooks/useBigCommerceSource";
import { claimShopifyStore } from "@/lib/hooks/useShopifySource";
import {
  createGenericApiKeySource,
  type GenericApiKeyPlatformKey,
} from "@/lib/hooks/useGenericApiKeySource";
import { createLightspeedSource } from "@/lib/hooks/useLightspeedSource";
import { createShopwareSource } from "@/lib/hooks/useShopwareSource";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";

const FILE_TYPES: FeedSourceType[] = ["csv", "json", "xml", "google_sheets"];
const ECOMMERCE_TYPES: FeedSourceType[] = ["woocommerce"];
// Four "URL + API key" e-commerce platforms served by the parametrised
// generic-API-key router on the backend (PrestaShop, OpenCart,
// Volusion, Cart Storefront). Lightspeed and Shopware have their own
// dedicated forms with platform-specific fields.
const GENERIC_API_KEY_TYPES: ReadonlySet<FeedSourceType> = new Set([
  "prestashop",
  "opencart",
  "volusion",
  "cart_storefront",
  "gomag",
  "contentspeed",
]);

type Step = "source_type" | "catalog_type" | "configure";

export default function NewSourcePage() {
  const router = useRouter();
  const { selectedId, selectedClient, isLoading: clientsLoading } = useFeedManagement();
  const { createSource, createShopifySource, testConnection } = useFeedSources(selectedId);
  const [step, setStep] = useState<Step>("source_type");
  const [selectedType, setSelectedType] = useState<FeedSourceType | null>(null);
  const [selectedCatalog, setSelectedCatalog] = useState<CatalogType>("product");
  const [selectedSubtype, setSelectedSubtype] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // When ``true``, the Shopify step renders the legacy ``ShopifySourceForm``
  // (manual Shop URL + agency-initiated OAuth) instead of the default
  // deferred-claim form. Toggled by the "Conectează manual" link on
  // ``ShopifyClaimForm`` so edge cases (no App Store access, reconnect
  // flows) keep working without losing functionality.
  const [shopifyManualMode, setShopifyManualMode] = useState(false);

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
      setShopifyManualMode(false);
      setError("");
    } else if (step === "catalog_type") {
      setSelectedType(null);
      setShopifyManualMode(false);
      setStep("source_type");
      setError("");
    } else {
      router.push("/agency/feed-management/sources");
    }
  }

  async function handleConnectShopify(data: { name: string; shop_domain: string }) {
    if (!selectedId) {
      setError("Selectează un client înainte de a crea sursa.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await createShopifySource({
        name: data.name,
        shop_domain: data.shop_domain,
        catalog_type: selectedCatalog,
        catalog_variant: selectedSubtype ?? "physical_products",
      });
      if (!result.authorize_url) {
        setError("Shopify OAuth nu este configurat pe server. Contactează administratorul.");
        return;
      }
      // Persist context across the OAuth round-trip so the callback page can recover it.
      sessionStorage.setItem(
        "shopify_oauth_context",
        JSON.stringify({
          source_id: result.source.id,
          client_id: selectedId,
          shop_domain: data.shop_domain,
          state: result.state,
          return_path: "/agency/feed-management/sources",
        }),
      );
      window.location.href = result.authorize_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la inițierea conexiunii Shopify.");
      setBusy(false);
    }
  }

  async function handleClaimShopify(data: ShopifyClaimFormData) {
    if (!selectedId) {
      setError("Selectează un client înainte de a crea sursa.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await claimShopifyStore(selectedId, {
        shop_domain: data.shop_domain,
        source_name: data.source_name,
        catalog_type: selectedCatalog,
        catalog_variant: selectedSubtype ?? "physical_products",
      });
      router.push("/agency/feed-management/sources");
    } catch (err) {
      // Surface a friendly message for the common 409 (already claimed)
      // case so the agency user knows the shop is bound to another row.
      const message =
        err instanceof Error ? err.message : "Eroare la revendicarea magazinului Shopify.";
      const isConflict = /already.*claim|409/i.test(message);
      setError(
        isConflict
          ? "Acest magazin Shopify este deja revendicat. Detașează sursa existentă mai întâi."
          : message,
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateLightspeed(data: LightspeedFormData) {
    if (!selectedId) {
      setError("Selectează un client înainte de a crea sursa.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createLightspeedSource(selectedId, {
        source_name: data.source_name,
        store_url: data.store_url,
        shop_id: data.shop_id,
        shop_language: data.shop_language,
        shop_region: data.shop_region,
        catalog_type: selectedCatalog,
        catalog_variant: selectedSubtype ?? "physical_products",
      });
      router.push("/agency/feed-management/sources");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Eroare la crearea sursei Lightspeed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateShopware(data: ShopwareFormData) {
    if (!selectedId) {
      setError("Selectează un client înainte de a crea sursa.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createShopwareSource(selectedId, {
        source_name: data.source_name,
        store_url: data.store_url,
        store_key: data.store_key,
        bridge_endpoint: data.bridge_endpoint,
        api_access_key: data.api_access_key,
        catalog_type: selectedCatalog,
        catalog_variant: selectedSubtype ?? "physical_products",
      });
      router.push("/agency/feed-management/sources");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Eroare la crearea sursei Shopware.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateGenericApiKey(
    platform: GenericApiKeyPlatformKey,
    data: GenericApiKeyFormData,
  ) {
    if (!selectedId) {
      setError("Selectează un client înainte de a crea sursa.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createGenericApiKeySource(platform, selectedId, {
        source_name: data.source_name,
        store_url: data.store_url,
        api_key: data.api_key,
        api_secret: data.api_secret,
        catalog_type: selectedCatalog,
        catalog_variant: selectedSubtype ?? "physical_products",
      });
      router.push("/agency/feed-management/sources");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Eroare la crearea sursei.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateMagento(data: MagentoConnectFormData) {
    if (!selectedId) {
      setError("Selectează un client înainte de a crea sursa.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createMagentoSourceApi(selectedId, {
        source_name: data.source_name,
        magento_base_url: data.magento_base_url,
        magento_store_code: data.magento_store_code,
        consumer_key: data.consumer_key,
        consumer_secret: data.consumer_secret,
        access_token: data.access_token,
        access_token_secret: data.access_token_secret,
        catalog_type: selectedCatalog,
        catalog_variant: selectedSubtype ?? "physical_products",
      });
      router.push("/agency/feed-management/sources");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la crearea sursei Magento.");
    } finally {
      setBusy(false);
    }
  }

  async function handleClaimBigCommerce(data: BigCommerceClaimFormData) {
    if (!selectedId) {
      setError("Selectează un client înainte de a crea sursa.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await claimBigCommerceStore(selectedId, {
        store_hash: data.store_hash,
        source_name: data.source_name,
        catalog_type: selectedCatalog,
        catalog_variant: selectedSubtype ?? "physical_products",
      });
      router.push("/agency/feed-management/sources");
    } catch (err) {
      // Surface a friendly message for the common 409 (already claimed)
      // case so the agency user knows the store is bound to another row.
      const message =
        err instanceof Error ? err.message : "Eroare la revendicarea magazinului BigCommerce.";
      const isConflict = /already.*claim|409/i.test(message);
      setError(
        isConflict
          ? "Acest magazin BigCommerce este deja revendicat. Detașează sursa existentă mai întâi."
          : message,
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleTestMagentoConnection(
    data: MagentoConnectFormData,
  ): Promise<MagentoTestConnectionResult> {
    try {
      const result = await testMagentoConnectionBeforeSave({
        magento_base_url: data.magento_base_url,
        magento_store_code: data.magento_store_code,
        consumer_key: data.consumer_key,
        consumer_secret: data.consumer_secret,
        access_token: data.access_token,
        access_token_secret: data.access_token_secret,
      });
      if (result.success) {
        return {
          success: true,
          message: `Conectat: ${result.store_name ?? "Magento store"}`,
          store_name: result.store_name,
          base_currency: result.base_currency,
        };
      }
      return {
        success: false,
        message: result.error ?? "Nu s-a putut valida conexiunea.",
      };
    } catch (err) {
      return {
        success: false,
        message: err instanceof Error ? err.message : "Eroare la testarea conexiunii.",
      };
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
      // Surface any optional HTTP Basic Auth credentials the file source
      // form may have included. The fields only appear for CSV / JSON /
      // XML sources; for other source types they're always undefined and
      // the extra keys get dropped by ``createSourceApi``.
      const authUsername = typeof data.feed_auth_username === "string"
        ? (data.feed_auth_username as string).trim()
        : "";
      const authPassword = typeof data.feed_auth_password === "string"
        ? (data.feed_auth_password as string)
        : "";

      await createSource({
        name: data.name as string,
        source_type: selectedType,
        catalog_type: selectedCatalog,
        url: (data.url ?? data.shop_url ?? data.store_url ?? "") as string,
        config: extractConfig(data),
        feed_auth_username: authUsername || undefined,
        feed_auth_password: authPassword || undefined,
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
              <CatalogTypeSelector
                selectedType={selectedCatalog}
                onSelect={handleSelectCatalogType}
                selectedSubtype={selectedSubtype}
                onSubtypeSelect={setSelectedSubtype}
              />
              <div className="mt-6 flex gap-3">
                <button type="button" onClick={handleBack} className="wm-btn-secondary">Înapoi</button>
                <button type="button" onClick={handleCatalogContinue} className="wm-btn-primary">Continuă</button>
              </div>
            </>
          )}

          {step === "configure" && selectedType !== null && (
            <div className="wm-card max-w-2xl p-6">
              {selectedType === "shopify" ? (
                shopifyManualMode ? (
                  <div className="space-y-3">
                    <button
                      type="button"
                      onClick={() => setShopifyManualMode(false)}
                      className="text-xs text-slate-500 underline-offset-2 hover:text-slate-700 hover:underline dark:text-slate-400 dark:hover:text-slate-200"
                      disabled={busy}
                    >
                      ← Înapoi la lista de magazine instalate
                    </button>
                    <ShopifySourceForm
                      onConnect={(data) => void handleConnectShopify(data)}
                      onCancel={handleBack}
                      busy={busy}
                    />
                  </div>
                ) : (
                  <ShopifyClaimForm
                    onClaim={(data) => void handleClaimShopify(data)}
                    onFallbackManual={() => setShopifyManualMode(true)}
                    onCancel={handleBack}
                    busy={busy}
                  />
                )
              ) : selectedType === "magento" ? (
                <MagentoSourceForm
                  onSubmit={(data) => void handleCreateMagento(data)}
                  onTestConnection={handleTestMagentoConnection}
                  onCancel={handleBack}
                  busy={busy}
                />
              ) : selectedType === "bigcommerce" ? (
                <BigCommerceClaimForm
                  onClaim={(data) => void handleClaimBigCommerce(data)}
                  onCancel={handleBack}
                  busy={busy}
                />
              ) : selectedType === "lightspeed" ? (
                <LightspeedSourceForm
                  onSubmit={(data) => void handleCreateLightspeed(data)}
                  onCancel={handleBack}
                  busy={busy}
                />
              ) : selectedType === "shopware" ? (
                <ShopwareSourceForm
                  onSubmit={(data) => void handleCreateShopware(data)}
                  onCancel={handleBack}
                  busy={busy}
                />
              ) : GENERIC_API_KEY_TYPES.has(selectedType) ? (
                <GenericApiKeySourceForm
                  platform={selectedType as GenericApiKeyPlatformKey}
                  onSubmit={(data) =>
                    void handleCreateGenericApiKey(
                      selectedType as GenericApiKeyPlatformKey,
                      data,
                    )
                  }
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
                  onSubmit={(data) =>
                    void handleCreate({
                      name: data.name,
                      url: data.url,
                      source_type: data.file_type,
                      feed_auth_username: data.feed_auth_username,
                      feed_auth_password: data.feed_auth_password,
                    })
                  }
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
