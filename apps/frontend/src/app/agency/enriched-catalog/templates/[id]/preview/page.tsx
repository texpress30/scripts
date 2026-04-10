"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Copy, Check } from "lucide-react";
import { useCreativeTemplate } from "@/lib/hooks/useCreativeTemplates";
import type { CanvasElement } from "@/lib/hooks/useCreativeTemplates";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useChannelProducts } from "@/lib/hooks/useChannelProducts";
import { useChannels } from "@/lib/hooks/useMasterFields";

interface RenderedPreview {
  product_index: number;
  image_url: string;
}

/** Load an image element with timeout. Returns null on failure. */
function loadImage(src: string, timeoutMs = 6000): Promise<HTMLImageElement | null> {
  return Promise.race([
    new Promise<HTMLImageElement | null>((resolve) => {
      const img = document.createElement("img");
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = src;
    }),
    new Promise<null>((resolve) => setTimeout(() => resolve(null), timeoutMs)),
  ]);
}

/**
 * Render a template with product data using raw Canvas 2D API.
 * Returns a data URL of the rendered image.
 */
async function renderTemplateForProduct(
  elements: CanvasElement[],
  canvasWidth: number,
  canvasHeight: number,
  backgroundColor: string,
  product: Record<string, unknown>,
): Promise<string> {
  const canvasEl = document.createElement("canvas");
  canvasEl.width = canvasWidth;
  canvasEl.height = canvasHeight;
  const ctx = canvasEl.getContext("2d")!;

  // Background
  ctx.fillStyle = backgroundColor;
  ctx.fillRect(0, 0, canvasWidth, canvasHeight);

  for (const el of elements) {
    // Replace dynamic bindings with product values
    let content = el.content || "";
    const binding = el.dynamic_binding;
    if (binding) {
      const fieldKey = binding.replace(/\{\{|\}\}/g, "").trim();
      content = String(product[fieldKey] ?? binding);
    }

    try {
      switch (el.type) {
        case "text":
        case "dynamic_field": {
          const fontSize = (el.style.font_size as number) || 16;
          const fontFamily = (el.style.font_family as string) || "Arial";
          const color = (el.style.color as string) || "#000000";
          ctx.font = `${fontSize}px ${fontFamily}`;
          ctx.fillStyle = color;
          ctx.textBaseline = "top";
          // Word-wrap text within width
          const maxWidth = el.width || canvasWidth - el.position_x;
          const words = content.split(" ");
          let line = "";
          let y = el.position_y;
          for (const word of words) {
            const testLine = line ? `${line} ${word}` : word;
            if (ctx.measureText(testLine).width > maxWidth && line) {
              ctx.fillText(line, el.position_x, y);
              line = word;
              y += fontSize * 1.3;
            } else {
              line = testLine;
            }
          }
          if (line) ctx.fillText(line, el.position_x, y);
          break;
        }
        case "image": {
          const imgUrl = binding
            ? String(product[binding.replace(/\{\{|\}\}/g, "").trim()] ?? content)
            : content;
          if (imgUrl && imgUrl.startsWith("http")) {
            // Try proxy first, then direct
            const proxyUrl = `/_next/image?url=${encodeURIComponent(imgUrl)}&w=${Math.max(Math.round(el.width || 400), 256)}&q=80`;
            let img = await loadImage(proxyUrl);
            if (!img) img = await loadImage(imgUrl);
            if (img) {
              const w = el.width || img.naturalWidth;
              const h = el.height || img.naturalHeight;
              ctx.drawImage(img, el.position_x, el.position_y, w, h);
            } else {
              // Placeholder
              ctx.fillStyle = "#e2e8f0";
              ctx.fillRect(el.position_x, el.position_y, el.width || 200, el.height || 200);
            }
          }
          break;
        }
        case "shape": {
          const shapeType = (el.style.shape_type as string) || el.content || "rectangle";
          const fill = (el.style.fill_color as string) || "#CCCCCC";
          ctx.fillStyle = fill;
          if (shapeType === "ellipse" || shapeType === "circle") {
            const rx = (el.width || 100) / 2;
            const ry = (el.height || 100) / 2;
            ctx.beginPath();
            ctx.ellipse(el.position_x + rx, el.position_y + ry, rx, ry, 0, 0, Math.PI * 2);
            ctx.fill();
          } else {
            ctx.fillRect(el.position_x, el.position_y, el.width || 200, el.height || 100);
          }
          break;
        }
      }
    } catch (err) {
      console.warn("Failed to render element:", err);
    }
  }

  try {
    return canvasEl.toDataURL("image/png");
  } catch {
    // Tainted canvas — retry without cross-origin images
    return canvasEl.toDataURL("image/jpeg", 0.8);
  }
}

export default function PreviewCreativesPage() {
  const params = useParams();
  const router = useRouter();
  const templateId = params.id as string;

  const { selectedId: subaccountId } = useFeedManagement();
  const { data: template } = useCreativeTemplate(templateId);

  // Feed data
  const { sources } = useFeedSources(subaccountId);
  const firstSourceId = sources.length > 0 ? sources[0].id : null;
  const { channels } = useChannels(firstSourceId);
  const firstChannelId = (channels?.length ?? 0) > 0 ? channels![0].id : null;
  const { products, total: totalProducts } = useChannelProducts(firstChannelId, 1, 48);

  const [rendering, setRendering] = useState(true);
  const [progress, setProgress] = useState(0);
  const [previews, setPreviews] = useState<RenderedPreview[]>([]);
  const [renderedCount, setRenderedCount] = useState(0);
  const [copied, setCopied] = useState(false);
  const renderingRef = useRef(false);

  useEffect(() => {
    if (!template || !products.length || renderingRef.current) return;
    renderingRef.current = true;

    const doRender = async () => {
      setRendering(true);
      setProgress(0);
      setPreviews([]);
      setRenderedCount(0);

      const maxPreviews = Math.min(products.length, 48);
      const results: RenderedPreview[] = [];

      for (let i = 0; i < maxPreviews; i++) {
        try {
          const dataUrl = await renderTemplateForProduct(
            template.elements,
            template.canvas_width,
            template.canvas_height,
            template.background_color,
            products[i],
          );
          results.push({ product_index: i, image_url: dataUrl });
        } catch (err) {
          console.warn(`Failed to render product ${i}:`, err);
          results.push({ product_index: i, image_url: "" });
        }
        setRenderedCount(results.length);
        setProgress(Math.round(((i + 1) / maxPreviews) * 100));
        setPreviews([...results]);
        // Yield to browser to update UI
        await new Promise((r) => setTimeout(r, 0));
      }

      setRendering(false);
    };

    doRender();
  }, [template, products]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCopyFeedUrl = () => {
    const feedUrl = `${window.location.origin}/api/feeds/${subaccountId}/enriched.csv`;
    navigator.clipboard.writeText(feedUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const maxPreviews = Math.min(products.length, 48);

  return (
    <div className="flex h-screen flex-col bg-slate-100 dark:bg-slate-900">
      {/* Breadcrumb top bar */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push(`/agency/enriched-catalog/templates/${templateId}/editor`)}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Edit Template
          </button>
          <span className="text-slate-300 dark:text-slate-600">&gt;</span>
          <span className="text-sm font-medium text-indigo-600 dark:text-indigo-400">Preview Creatives</span>
          <span className="text-slate-300 dark:text-slate-600">&gt;</span>
          <span className="text-sm text-slate-400">Select Output Feed</span>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span>{totalProducts} SKUs</span>
          {template && <span>{template.canvas_width} X {template.canvas_height}</span>}
        </div>
      </div>

      {/* Template name + info bar */}
      <div className="border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-700 dark:bg-slate-800">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">{template?.name || "Template"}</p>
        {maxPreviews > 0 && (
          <p className="text-[10px] text-slate-400">*This is a sample of up to {maxPreviews} rows from the Enriched Catalog Feed</p>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main content: progress or grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {rendering && progress < 100 ? (
            <div className="flex items-center justify-center py-20">
              <div className="flex w-96 flex-col items-center gap-4 rounded-xl bg-white p-8 shadow-sm dark:bg-slate-800">
                <div className="text-4xl font-bold text-slate-700 dark:text-slate-200">{progress}%</div>
                <p className="text-sm text-slate-500 dark:text-slate-400">Lining up your previews...</p>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-xs text-slate-400">{renderedCount} / {maxPreviews} rendered</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
              {previews.map((preview, idx) => (
                <div
                  key={idx}
                  className="group relative overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm transition hover:shadow-md dark:border-slate-700 dark:bg-slate-800"
                >
                  <img
                    src={preview.image_url}
                    alt={`Preview ${idx + 1}`}
                    className="w-full object-contain"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right sidebar: stats + Add to Feed */}
        <div className="w-72 shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          {/* Stats */}
          <div className="mb-4 flex items-center gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{totalProducts}</p>
              <p className="text-[10px] text-slate-400">Product Rows</p>
            </div>
            <div className="h-10 w-px bg-slate-200 dark:bg-slate-700" />
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-700 dark:text-slate-200">{renderedCount}</p>
              <p className="text-[10px] text-slate-400">Rendered</p>
            </div>
            {rendering && (
              <>
                <div className="h-10 w-px bg-slate-200 dark:bg-slate-700" />
                <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
              </>
            )}
          </div>

          {/* Add to Feed button */}
          <button className="mb-6 w-full rounded-lg bg-emerald-500 py-2.5 text-sm font-medium text-white shadow hover:bg-emerald-600">
            Add to Feed
          </button>

          {/* What is next */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300">What is next?</h4>

            <div className="space-y-2 text-xs text-slate-500 dark:text-slate-400">
              <p>
                <span className="font-medium text-slate-600 dark:text-slate-300">1.</span> Publish design to an output feed slot. You are able to add multiple designs in a feed.
                <span className="font-medium text-indigo-600 dark:text-indigo-400"> Copy the feed URL</span> once the feed is finished generating.
              </p>

              {/* Output feed card */}
              <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-medium text-slate-600 dark:text-slate-300">Output Feed</p>
                    <p className="text-[10px] text-slate-400">{renderedCount > 0 ? "1" : "0"} DESIGNS</p>
                  </div>
                  <button
                    onClick={handleCopyFeedUrl}
                    className="flex items-center gap-1 rounded px-2 py-1 text-[10px] text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700"
                  >
                    {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                    {copied ? "Copied!" : "Copy URL"}
                  </button>
                </div>
              </div>

              <p>
                <span className="font-medium text-slate-600 dark:text-slate-300">2.</span> Paste the enriched feed URL into your ad platform. Once uploaded, changes sync as new products are added and removed.
              </p>
              <p>
                <span className="font-medium text-slate-600 dark:text-slate-300">3.</span> Build campaigns using your enriched feed designs.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
