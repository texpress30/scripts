"use client";

import { useRef, useState } from "react";
import { Loader2, Upload } from "lucide-react";

import {
  completeDirectUpload,
  initDirectUpload,
  uploadFileToPresignedUrl,
  uploadFileViaBackend,
  type StorageKind,
} from "@/lib/storage-client";

type MediaUploadZoneProps = {
  clientId: number;
  folderId: string | null;
  accept?: string;
  onUploaded?: () => void;
  onError?: (message: string) => void;
  label?: string;
};

function detectKind(file: File): StorageKind {
  const mime = String(file.type || "").toLowerCase();
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  return "document";
}

export function MediaUploadZone({
  clientId,
  folderId,
  accept,
  onUploaded,
  onError,
  label = "Upload",
}: MediaUploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [progressLabel, setProgressLabel] = useState<string | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    let completedCount = 0;
    try {
      for (const file of Array.from(files)) {
        setProgressLabel(`Încarc ${file.name}...`);
        const kind = detectKind(file);
        try {
          // Fast path: browser → S3 presigned PUT
          const init = await initDirectUpload({
            clientId,
            kind,
            fileName: file.name,
            mimeType: file.type || "application/octet-stream",
            sizeBytes: file.size,
            folderId,
          });
          await uploadFileToPresignedUrl({
            url: init.upload.url,
            file,
            method: init.upload.method,
            headers: init.upload.headers,
          });
          await completeDirectUpload({
            clientId,
            mediaId: init.media_id,
          });
        } catch (err) {
          // Fallback: backend-proxied upload. The browser-direct PUT fails with
          // a low-level TypeError ("Failed to fetch") when the S3 bucket's CORS
          // policy doesn't include the current origin (or on mixed-content /
          // offline scenarios). Route the file through the FastAPI server in
          // that case instead of surfacing the error to the user.
          const isNetworkError =
            err instanceof TypeError ||
            (err instanceof Error && /failed to fetch/i.test(err.message));
          if (!isNetworkError) throw err;
          setProgressLabel(`Încarc ${file.name} (fallback)...`);
          await uploadFileViaBackend({
            clientId,
            kind,
            file,
            folderId,
          });
        }
        completedCount += 1;
      }
      setProgressLabel(null);
      if (completedCount > 0) onUploaded?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload-ul a eșuat.";
      setProgressLabel(null);
      onError?.(message);
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        multiple
        className="hidden"
        onChange={(event) => void handleFiles(event.target.files)}
      />
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        className="wm-btn-primary inline-flex items-center gap-2 text-sm"
        disabled={busy}
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
        {busy && progressLabel ? progressLabel : label}
      </button>
    </>
  );
}
