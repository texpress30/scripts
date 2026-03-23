"use client";

import React from "react";
import { useEffect, useState } from "react";
import {
  Palette,
  Image,
  FileText,
  Video,
  Plus,
  Search,
  Eye,
  Download,
  MoreHorizontal,
  CheckCircle2,
  Clock,
  AlertCircle,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { CreativeMediaLibrary, type CreativeMediaItem } from "@/components/CreativeMediaLibrary";

type CreativeClient = { id: number; name: string };

type CreativeAsset = {
  id: number;
  name: string;
  type: "image" | "video" | "copy" | "banner";
  status: "approved" | "in_review" | "draft";
  client_name: string;
  platform: string;
  updated_at: string;
};

const statusConfig = {
  approved: {
    label: "Aprobat",
    icon: CheckCircle2,
    className: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  },
  in_review: {
    label: "In Review",
    icon: Clock,
    className: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  },
  draft: {
    label: "Draft",
    icon: AlertCircle,
    className: "bg-muted text-muted-foreground",
  },
};

const typeIcons = {
  image: Image,
  video: Video,
  copy: FileText,
  banner: Palette,
};

// Placeholder data — replace with apiRequest calls to your FastAPI backend
const placeholderAssets: CreativeAsset[] = [
  {
    id: 1,
    name: "Banner campanie vara 2025",
    type: "banner",
    status: "approved",
    client_name: "Acme Corp",
    platform: "Google Ads",
    updated_at: "2025-06-12",
  },
  {
    id: 2,
    name: "Video promo produs nou",
    type: "video",
    status: "in_review",
    client_name: "TechStart SRL",
    platform: "Meta",
    updated_at: "2025-06-10",
  },
  {
    id: 3,
    name: "Ad copy — oferta speciala",
    type: "copy",
    status: "draft",
    client_name: "Acme Corp",
    platform: "Google Ads",
    updated_at: "2025-06-09",
  },
  {
    id: 4,
    name: "Story Instagram — testimonial",
    type: "image",
    status: "approved",
    client_name: "FreshBite",
    platform: "Meta",
    updated_at: "2025-06-08",
  },
  {
    id: 5,
    name: "Carousel Facebook — features",
    type: "image",
    status: "in_review",
    client_name: "TechStart SRL",
    platform: "Meta",
    updated_at: "2025-06-07",
  },
];

export default function CreativePage() {
  const [assets] = useState<CreativeAsset[]>(placeholderAssets);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [creativeClients, setCreativeClients] = useState<CreativeClient[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [selectedMedia, setSelectedMedia] = useState<CreativeMediaItem | null>(null);

  // TODO: Replace with real API call
  // useEffect(() => {
  //   async function load() {
  //     const result = await apiRequest<{ items: CreativeAsset[] }>("/creatives");
  //     setAssets(result.items);
  //   }
  //   void load();
  // }, []);

  useEffect(() => {
    let ignore = false;
    async function loadClientsForMediaLibrary() {
      try {
        const payload = await apiRequest<{ items: CreativeClient[] }>("/clients");
        const items = Array.isArray(payload.items)
          ? payload.items
              .map((item) => ({ id: Number(item.id || 0), name: String(item.name || "").trim() }))
              .filter((item) => item.id > 0 && item.name !== "")
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

    void loadClientsForMediaLibrary();
    return () => {
      ignore = true;
    };
  }, []);

  const filtered = assets.filter((a) => {
    const matchesSearch = a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.client_name.toLowerCase().includes(searchQuery.toLowerCase());
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
          <p className="text-sm text-muted-foreground">
            Gestioneaza asset-urile creative pentru campaniile tale — bannere, video-uri, copy si altele.
          </p>
        </div>

        {/* Stats row */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Total Assets", value: counts.total, color: "text-foreground" },
            { label: "Aprobate", value: counts.approved, color: "text-emerald-600 dark:text-emerald-400" },
            { label: "In Review", value: counts.in_review, color: "text-amber-600 dark:text-amber-400" },
            { label: "Draft", value: counts.draft, color: "text-muted-foreground" },
          ].map((stat) => (
            <div key={stat.label} className="mcc-card flex flex-col gap-1 p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {stat.label}
              </span>
              <span className={`text-2xl font-semibold ${stat.color}`}>{stat.value}</span>
            </div>
          ))}
        </div>

        {/* Toolbar */}
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cauta asset-uri..."
              className="mcc-input pl-10"
            />
          </div>
          <div className="flex items-center gap-2">
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="mcc-input h-9 text-sm"
            >
              <option value="all">Toate tipurile</option>
              <option value="image">Imagini</option>
              <option value="video">Video</option>
              <option value="copy">Copy</option>
              <option value="banner">Bannere</option>
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="mcc-input h-9 text-sm"
            >
              <option value="all">Toate statusurile</option>
              <option value="approved">Aprobat</option>
              <option value="in_review">In Review</option>
              <option value="draft">Draft</option>
            </select>
            <button className="mcc-btn-primary gap-2">
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">Adauga</span>
            </button>
          </div>
        </div>

        {/* Assets table */}
        <div className="mcc-card overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Asset
                </th>
                <th className="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground sm:table-cell">
                  Tip
                </th>
                <th className="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground md:table-cell">
                  Client
                </th>
                <th className="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground lg:table-cell">
                  Platforma
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Status
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Actiuni
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((asset) => {
                const TypeIcon = typeIcons[asset.type];
                const status = statusConfig[asset.status];
                const StatusIcon = status.icon;
                return (
                  <tr
                    key={asset.id}
                    className="border-b border-border transition-colors hover:bg-muted/30"
                  >
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
                    <td className="hidden px-4 py-3 capitalize text-muted-foreground sm:table-cell">
                      {asset.type}
                    </td>
                    <td className="hidden px-4 py-3 text-foreground md:table-cell">
                      {asset.client_name}
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
                      {asset.platform}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}>
                        <StatusIcon className="h-3 w-3" />
                        {status.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                          <Eye className="h-4 w-4" />
                        </button>
                        <button className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                          <Download className="h-4 w-4" />
                        </button>
                        <button className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                          <MoreHorizontal className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td className="px-4 py-8 text-center text-muted-foreground" colSpan={6}>
                    {searchQuery
                      ? "Niciun asset gasit pentru cautarea ta."
                      : "Nu exista asset-uri creative inca."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-6 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold text-foreground">Creative Media Library</h2>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Client</span>
              <select
                className="mcc-input h-9 text-sm"
                value={selectedClientId ?? ""}
                onChange={(event) => setSelectedClientId(event.target.value ? Number(event.target.value) : null)}
                data-testid="creative-media-client-select"
              >
                {creativeClients.length === 0 ? <option value="">Niciun client</option> : null}
                {creativeClients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <CreativeMediaLibrary clientId={selectedClientId} onSelectMedia={setSelectedMedia} />
          {selectedMedia ? (
            <p className="text-sm text-muted-foreground" data-testid="creative-selected-media-hint">
              Media selectată local pentru pasul următor: <span className="font-mono">{selectedMedia.media_id}</span>
            </p>
          ) : (
            <p className="text-sm text-muted-foreground" data-testid="creative-selected-media-hint">Nu ai selectat încă media pentru pasul următor.</p>
          )}
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
