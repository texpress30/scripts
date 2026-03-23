"use client";

import React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Palette,
  Image,
  FileText,
  Video,
  Plus,
  Search,
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { CreativeMediaLibrary, type CreativeMediaItem } from "@/components/CreativeMediaLibrary";
import { apiRequest } from "@/lib/api";
import { getMediaAccessUrl } from "@/lib/storage-client";

type CreativeClient = { id: number; name: string };

type CreativeVariant = {
  id: number;
  headline: string;
  body: string;
  cta: string;
  media?: string;
  media_id?: string | null;
  approval_status?: string;
};

type CreativeAssetApiItem = {
  id?: number;
  client_id?: number;
  name?: string;
  metadata?: {
    format?: string;
    platform_fit?: string[];
    approval_status?: string;
  };
  creative_variants?: CreativeVariant[];
};

type CreativeAsset = {
  id: number;
  name: string;
  type: "image" | "video" | "copy" | "banner";
  status: "approved" | "in_review" | "draft";
  client_name: string;
  platform: string;
  updated_at: string;
};

type AddVariantResponse = { id: number; asset_id: number; media_id?: string | null; media?: string };

const statusConfig = {
  approved: { label: "Aprobat", icon: CheckCircle2, className: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  in_review: { label: "In Review", icon: Clock, className: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  draft: { label: "Draft", icon: AlertCircle, className: "bg-muted text-muted-foreground" },
};

const typeIcons = { image: Image, video: Video, copy: FileText, banner: Palette };

const placeholderAssets: CreativeAsset[] = [
  { id: 1, name: "Banner campanie vara 2025", type: "banner", status: "approved", client_name: "Acme Corp", platform: "Google Ads", updated_at: "2025-06-12" },
  { id: 2, name: "Video promo produs nou", type: "video", status: "in_review", client_name: "TechStart SRL", platform: "Meta", updated_at: "2025-06-10" },
  { id: 3, name: "Ad copy — oferta speciala", type: "copy", status: "draft", client_name: "Acme Corp", platform: "Google Ads", updated_at: "2025-06-09" },
];

function toCreativeAsset(item: CreativeAssetApiItem, clientName: string): CreativeAsset {
  const format = String(item.metadata?.format || "").toLowerCase();
  const type: CreativeAsset["type"] = format === "video" || format === "copy" || format === "banner" ? (format as CreativeAsset["type"]) : "image";
  const statusRaw = String(item.metadata?.approval_status || "draft").toLowerCase();
  const status: CreativeAsset["status"] = statusRaw === "approved" ? "approved" : statusRaw === "in_review" ? "in_review" : "draft";
  return {
    id: Number(item.id || 0),
    name: String(item.name || "Asset"),
    type,
    status,
    client_name: clientName,
    platform: (item.metadata?.platform_fit || ["-"])[0] || "-",
    updated_at: "-",
  };
}

function resolveLegacyMedia(selectedMedia: CreativeMediaItem): string {
  const filename = String(selectedMedia.original_filename || "").trim();
  if (filename !== "") return filename;
  return `media:${selectedMedia.media_id}`;
}

function looksLikeVideo(value: string): boolean {
  return /\.(mp4|webm|mov|m4v)(\?.*)?$/i.test(value);
}

export default function CreativePage() {
  const [assets, setAssets] = useState<CreativeAsset[]>(placeholderAssets);
  const [assetDetails, setAssetDetails] = useState<CreativeAssetApiItem[]>([]);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [assetsError, setAssetsError] = useState("");

  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const [creativeClients, setCreativeClients] = useState<CreativeClient[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [selectedMedia, setSelectedMedia] = useState<CreativeMediaItem | null>(null);

  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null);
  const [variantPreviewUrl, setVariantPreviewUrl] = useState("");
  const [variantPreviewMimeType, setVariantPreviewMimeType] = useState("");
  const [variantPreviewLoading, setVariantPreviewLoading] = useState(false);
  const [variantPreviewError, setVariantPreviewError] = useState("");

  const [variantHeadline, setVariantHeadline] = useState("Primary headline");
  const [variantBody, setVariantBody] = useState("Descriere scurtă pentru variantă.");
  const [variantCta, setVariantCta] = useState("Afla mai mult");
  const [addVariantLoading, setAddVariantLoading] = useState(false);
  const [addVariantError, setAddVariantError] = useState("");
  const [addVariantSuccess, setAddVariantSuccess] = useState("");

  useEffect(() => {
    let ignore = false;
    async function loadClients() {
      try {
        const payload = await apiRequest<{ items: CreativeClient[] }>("/clients");
        const items = Array.isArray(payload.items)
          ? payload.items.map((i) => ({ id: Number(i.id || 0), name: String(i.name || "").trim() })).filter((i) => i.id > 0 && i.name !== "")
          : [];
        if (!ignore) {
          setCreativeClients(items);
          setSelectedClientId((prev) => (prev && items.some((item) => item.id === prev) ? prev : items[0]?.id ?? null));
        }
      } catch {
        if (!ignore) {
          setCreativeClients([]);
          setSelectedClientId(null);
        }
      }
    }
    void loadClients();
    return () => {
      ignore = true;
    };
  }, []);

  const loadAssets = useCallback(async () => {
    if (!selectedClientId) {
      setAssets(placeholderAssets);
      setAssetDetails([]);
      setSelectedAssetId(null);
      return;
    }

    setAssetsLoading(true);
    setAssetsError("");
    try {
      const payload = await apiRequest<{ items: CreativeAssetApiItem[] }>(`/creative/library/assets?client_id=${selectedClientId}`);
      const details = Array.isArray(payload.items) ? payload.items : [];
      const clientName = creativeClients.find((c) => c.id === selectedClientId)?.name ?? `Client #${selectedClientId}`;
      const mapped = details.map((item) => toCreativeAsset(item, clientName)).filter((item) => item.id > 0);
      setAssetDetails(details);
      setAssets(mapped.length > 0 ? mapped : []);
      setSelectedAssetId((prev) => {
        if (prev && mapped.some((item) => item.id === prev)) return prev;
        return mapped[0]?.id ?? null;
      });
    } catch (err) {
      setAssetsError(err instanceof Error ? err.message : "Nu am putut încărca asset-urile creative.");
    } finally {
      setAssetsLoading(false);
    }
  }, [creativeClients, selectedClientId]);

  useEffect(() => {
    void loadAssets();
  }, [loadAssets]);

  const selectedAssetDetail = useMemo(
    () => assetDetails.find((item) => Number(item.id || 0) === Number(selectedAssetId || 0)) ?? null,
    [assetDetails, selectedAssetId],
  );

  const variants = useMemo(() => {
    if (!selectedAssetDetail || !Array.isArray(selectedAssetDetail.creative_variants)) return [];
    return selectedAssetDetail.creative_variants;
  }, [selectedAssetDetail]);

  useEffect(() => {
    setSelectedVariantId((prev) => {
      if (prev && variants.some((v) => v.id === prev)) return prev;
      return variants[0]?.id ?? null;
    });
  }, [variants]);

  const selectedVariant = useMemo(() => variants.find((item) => item.id === selectedVariantId) ?? null, [variants, selectedVariantId]);

  useEffect(() => {
    if (!selectedVariant || !selectedVariant.media_id || !selectedClientId) {
      setVariantPreviewUrl("");
      setVariantPreviewMimeType("");
      setVariantPreviewError(selectedVariant && !selectedVariant.media_id ? "Varianta are doar media legacy (fără media_id)." : "");
      setVariantPreviewLoading(false);
      return;
    }

    let ignore = false;
    setVariantPreviewLoading(true);
    setVariantPreviewError("");
    async function loadVariantPreview() {
      try {
        const access = await getMediaAccessUrl({ clientId: selectedClientId, mediaId: selectedVariant.media_id as string, disposition: "inline" });
        if (!ignore) {
          setVariantPreviewUrl(String(access.url || "").trim());
          setVariantPreviewMimeType(String(access.mime_type || "").trim());
        }
      } catch (err) {
        if (!ignore) {
          setVariantPreviewUrl("");
          setVariantPreviewMimeType("");
          setVariantPreviewError(err instanceof Error ? err.message : "Preview indisponibil pentru această variantă.");
        }
      } finally {
        if (!ignore) setVariantPreviewLoading(false);
      }
    }

    void loadVariantPreview();
    return () => {
      ignore = true;
    };
  }, [selectedClientId, selectedVariant]);

  async function onAddVariantToSelectedAsset() {
    setAddVariantError("");
    setAddVariantSuccess("");

    if (!selectedAssetId) {
      setAddVariantError("Selectează mai întâi un asset din listă.");
      return;
    }
    if (!selectedMedia) {
      setAddVariantError("Selectează media din Creative Media Library înainte să adaugi varianta.");
      return;
    }

    setAddVariantLoading(true);
    try {
      const payload = {
        headline: variantHeadline.trim() || "Headline",
        body: variantBody.trim() || "Body",
        cta: variantCta.trim() || "Afla mai mult",
        media_id: selectedMedia.media_id,
        media: resolveLegacyMedia(selectedMedia),
      };
      const result = await apiRequest<AddVariantResponse>(`/creative/library/assets/${selectedAssetId}/variants`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setAddVariantSuccess(`Varianta #${result.id} a fost adăugată pe asset #${selectedAssetId}.`);
      await loadAssets();
      setSelectedVariantId(result.id);
    } catch (err) {
      setAddVariantError(err instanceof Error ? err.message : "Nu am putut adăuga varianta.");
    } finally {
      setAddVariantLoading(false);
    }
  }

  const filtered = assets.filter((a) => {
    const matchesSearch = a.name.toLowerCase().includes(searchQuery.toLowerCase()) || a.client_name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === "all" || a.type === filterType;
    const matchesStatus = filterStatus === "all" || a.status === filterStatus;
    return matchesSearch && matchesType && matchesStatus;
  });

  const counts = {
    total: assets.length,
    approved: assets.filter((a) => a.status === "approved").length,
    in_review: assets.filter((a) => a.status === "in_review").length,
    draft: assets.filter((a) => a.status === "draft").length,
  };

  return (
    <ProtectedPage>
      <AppShell title="Creative">
        <div className="mb-6">
          <p className="text-sm text-muted-foreground">Gestioneaza asset-urile creative pentru campaniile tale — bannere, video-uri, copy si altele.</p>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Total Assets", value: counts.total, color: "text-foreground" },
            { label: "Aprobate", value: counts.approved, color: "text-emerald-600 dark:text-emerald-400" },
            { label: "In Review", value: counts.in_review, color: "text-amber-600 dark:text-amber-400" },
            { label: "Draft", value: counts.draft, color: "text-muted-foreground" },
          ].map((stat) => (
            <div key={stat.label} className="mcc-card flex flex-col gap-1 p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{stat.label}</span>
              <span className={`text-2xl font-semibold ${stat.color}`}>{stat.value}</span>
            </div>
          ))}
        </div>

        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Cauta asset-uri..." className="mcc-input pl-10" />
          </div>
          <div className="flex items-center gap-2">
            <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="mcc-input h-9 text-sm">
              <option value="all">Toate tipurile</option>
              <option value="image">Imagini</option>
              <option value="video">Video</option>
              <option value="copy">Copy</option>
              <option value="banner">Bannere</option>
            </select>
            <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="mcc-input h-9 text-sm">
              <option value="all">Toate statusurile</option>
              <option value="approved">Aprobat</option>
              <option value="in_review">In Review</option>
              <option value="draft">Draft</option>
            </select>
            <button className="mcc-btn-primary gap-2" type="button">
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">Adauga</span>
            </button>
          </div>
        </div>

        <div className="mcc-card overflow-hidden" data-testid="creative-assets-table">
          {assetsLoading ? (
            <div className="flex items-center gap-2 px-4 py-5 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Se încarcă asset-urile...
            </div>
          ) : (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Asset</th>
                  <th className="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground sm:table-cell">Tip</th>
                  <th className="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground md:table-cell">Client</th>
                  <th className="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground lg:table-cell">Platforma</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Status</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Actiuni</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((asset) => {
                  const TypeIcon = typeIcons[asset.type];
                  const status = statusConfig[asset.status];
                  const StatusIcon = status.icon;
                  const selected = selectedAssetId === asset.id;
                  return (
                    <tr key={asset.id} className={`border-b border-border transition-colors hover:bg-muted/30 ${selected ? "bg-indigo-50/50" : ""}`}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                            <TypeIcon className="h-4 w-4 text-primary" />
                          </div>
                          <div className="min-w-0">
                            <p className="truncate font-medium text-foreground">{asset.name}</p>
                            <p className="text-xs text-muted-foreground sm:hidden">{asset.client_name}</p>
                          </div>
                        </div>
                      </td>
                      <td className="hidden px-4 py-3 capitalize text-muted-foreground sm:table-cell">{asset.type}</td>
                      <td className="hidden px-4 py-3 text-foreground md:table-cell">{asset.client_name}</td>
                      <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">{asset.platform}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}>
                          <StatusIcon className="h-3 w-3" />
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button type="button" className="rounded-md border px-2 py-1 text-xs" onClick={() => setSelectedAssetId(asset.id)} data-testid={`select-asset-${asset.id}`}>
                          Selectează
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td className="px-4 py-8 text-center text-muted-foreground" colSpan={6}>
                      {searchQuery ? "Niciun asset gasit pentru cautarea ta." : "Nu exista asset-uri creative inca."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        <div className="mt-6 space-y-3 rounded-md border border-border bg-muted/20 p-4" data-testid="creative-asset-detail">
          <h2 className="text-base font-semibold text-foreground">Asset detail + variants</h2>
          {!selectedAssetId ? (
            <p className="text-sm text-muted-foreground">Selectează un asset din listă pentru a vedea variantele și preview-ul.</p>
          ) : assetsError ? (
            <p className="text-sm text-red-700">Nu am putut încărca detaliile asset-ului selectat: {assetsError}</p>
          ) : selectedAssetDetail === null ? (
            <p className="text-sm text-muted-foreground">Se încarcă detaliile asset-ului...</p>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">Asset selectat: <span className="font-medium text-foreground">#{selectedAssetId} {selectedAssetDetail.name || "Asset"}</span></p>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
                <div className="space-y-2">
                  {variants.length === 0 ? (
                    <p className="rounded-md border border-border px-3 py-3 text-sm text-muted-foreground">Asset-ul selectat nu are variante încă.</p>
                  ) : (
                    <ul className="space-y-2" data-testid="asset-variants-list">
                      {variants.map((variant) => {
                        const selected = variant.id === selectedVariantId;
                        return (
                          <li key={variant.id}>
                            <button
                              type="button"
                              className={`w-full rounded-md border px-3 py-2 text-left ${selected ? "border-indigo-500 bg-indigo-50" : "border-border hover:bg-muted/40"}`}
                              onClick={() => setSelectedVariantId(variant.id)}
                              data-testid={`asset-variant-${variant.id}`}
                            >
                              <p className="text-sm font-medium">Variant #{variant.id} — {variant.headline || "(fără headline)"}</p>
                              <p className="mt-1 text-xs text-muted-foreground">CTA: {variant.cta || "-"}</p>
                              <p className="mt-1 text-xs text-muted-foreground">Approval: {variant.approval_status ? variant.approval_status : "-"}</p>
                              <p className="mt-1 text-xs text-muted-foreground">media_id: {variant.media_id ? variant.media_id : "lipsă"}</p>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>

                <aside className="rounded-md border border-border bg-background p-3" data-testid="asset-variant-preview">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Preview variantă</p>
                  {!selectedVariant ? (
                    <p className="mt-3 text-sm text-muted-foreground">Selectează o variantă.</p>
                  ) : variantPreviewLoading ? (
                    <p className="mt-3 text-sm text-muted-foreground">Se încarcă preview...</p>
                  ) : variantPreviewError ? (
                    <p className="mt-3 text-sm text-amber-700">{variantPreviewError}</p>
                  ) : variantPreviewUrl === "" ? (
                    <p className="mt-3 text-sm text-muted-foreground">Preview indisponibil.</p>
                  ) : variantPreviewMimeType.startsWith("video/") || looksLikeVideo(variantPreviewUrl) || looksLikeVideo(String(selectedVariant.media || "")) ? (
                    <video controls src={variantPreviewUrl} className="mt-3 max-h-60 w-full rounded" data-testid="variant-preview-video" />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={variantPreviewUrl} alt="variant preview" className="mt-3 max-h-60 w-full rounded object-contain" data-testid="variant-preview-image" />
                  )}
                </aside>
              </div>
            </>
          )}
        </div>

        <div className="mt-6 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold text-foreground">Creative Media Library</h2>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Client</span>
              <select className="mcc-input h-9 text-sm" value={selectedClientId ?? ""} onChange={(e) => setSelectedClientId(e.target.value ? Number(e.target.value) : null)} data-testid="creative-media-client-select">
                {creativeClients.length === 0 ? <option value="">Niciun client</option> : null}
                {creativeClients.map((client) => (
                  <option key={client.id} value={client.id}>{client.name}</option>
                ))}
              </select>
            </div>
          </div>

          <CreativeMediaLibrary clientId={selectedClientId} onSelectMedia={setSelectedMedia} />
          {selectedMedia ? (
            <p className="text-sm text-muted-foreground" data-testid="creative-selected-media-hint">
              Media selectată local pentru pasul următor: <span className="font-mono">{selectedMedia.media_id}</span> ({selectedMedia.kind})
            </p>
          ) : (
            <p className="text-sm text-muted-foreground" data-testid="creative-selected-media-hint">Nu ai selectat încă media pentru pasul următor.</p>
          )}
        </div>

        <div className="mt-6 space-y-3 rounded-md border border-border bg-muted/20 p-4" data-testid="creative-add-variant-flow">
          <h2 className="text-base font-semibold text-foreground">Add variant pe asset existent</h2>
          {!selectedAssetId ? <p className="text-sm text-muted-foreground">Alege mai întâi un asset din listă.</p> : null}
          {addVariantError ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{addVariantError}</div> : null}
          {addVariantSuccess ? <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{addVariantSuccess}</div> : null}

          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm text-slate-700 md:col-span-2">
              Headline
              <input value={variantHeadline} onChange={(e) => setVariantHeadline(e.target.value)} className="mcc-input mt-1" data-testid="add-variant-headline" />
            </label>
            <label className="text-sm text-slate-700 md:col-span-2">
              Body
              <textarea value={variantBody} onChange={(e) => setVariantBody(e.target.value)} className="mcc-input mt-1 min-h-20" data-testid="add-variant-body" />
            </label>
            <label className="text-sm text-slate-700 md:col-span-2">
              CTA
              <input value={variantCta} onChange={(e) => setVariantCta(e.target.value)} className="mcc-input mt-1" data-testid="add-variant-cta" />
            </label>
          </div>

          <button
            type="button"
            className="mcc-btn-primary gap-2"
            onClick={() => void onAddVariantToSelectedAsset()}
            disabled={addVariantLoading || !selectedAssetId || !selectedMedia}
            data-testid="add-variant-button"
          >
            {addVariantLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add variant with selected media
          </button>
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
