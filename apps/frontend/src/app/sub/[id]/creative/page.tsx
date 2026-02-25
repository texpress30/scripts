"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

type CreativeAsset = {
  id: number;
  client_id: number;
  name: string;
  metadata: { approval_status: string; legal_status: string };
};

export default function SubCreativePage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);

  const [assets, setAssets] = useState<CreativeAsset[]>([]);
  const [name, setName] = useState("New Asset");
  const [error, setError] = useState("");

  async function loadAssets() {
    setError("");
    try {
      const response = await apiRequest<{ items: CreativeAsset[] }>(`/creative/library/assets?client_id=${clientId}`);
      setAssets(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot încărca asset-urile");
    }
  }

  useEffect(() => {
    if (Number.isFinite(clientId)) void loadAssets();
  }, [clientId]);

  async function createAsset(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await apiRequest("/creative/library/assets", {
        method: "POST",
        body: JSON.stringify({
          client_id: clientId,
          name,
          format: "image",
          dimensions: "1080x1080",
          objective_fit: "performance",
          platform_fit: ["google", "meta"],
          language: "ro",
          brand_tags: ["default"],
          legal_status: "pending",
          approval_status: "draft",
        }),
      });
      await loadAssets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot crea asset");
    }
  }

  return (
    <ProtectedPage>
      <AppShell title={`Sub Creative · #${clientId}`}>
        {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}

        <form onSubmit={createAsset} className="mb-4 flex gap-3">
          <input className="wm-input" value={name} onChange={(e) => setName(e.target.value)} required />
          <button className="wm-btn-primary disabled:opacity-50" disabled={readOnly} title={readOnly ? "Read-only" : undefined}>
            Create asset
          </button>
        </form>

        <section className="wm-card overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Approval</th>
                <th className="px-4 py-3">Legal</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr key={asset.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">{asset.id}</td>
                  <td className="px-4 py-3">{asset.name}</td>
                  <td className="px-4 py-3">{asset.metadata.approval_status}</td>
                  <td className="px-4 py-3">{asset.metadata.legal_status}</td>
                </tr>
              ))}
              {assets.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-3 text-slate-500">Nu există asset-uri.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>
      </AppShell>
    </ProtectedPage>
  );
}
