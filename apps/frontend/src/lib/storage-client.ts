import { apiRequest } from "@/lib/api";

export type StorageKind = "image" | "video" | "document";

export type StorageUploadInitResponse = {
  media_id: string;
  status: string;
  bucket: string;
  key: string;
  region: string;
  upload: {
    method: string;
    url: string;
    expires_in: number;
    headers: Record<string, string>;
  };
};

export type StorageUploadCompleteResponse = {
  media_id: string;
  status: string;
  bucket: string;
  key: string;
  region: string;
  mime_type: string;
  size_bytes?: number | null;
  uploaded_at?: string | null;
  etag?: string | null;
  version_id?: string | null;
};

export type StorageAccessUrlResponse = {
  media_id: string;
  status: string;
  mime_type: string;
  method: string;
  url: string;
  expires_in: number;
  disposition: "inline" | "attachment";
  filename: string;
};

export async function initDirectUpload(params: {
  clientId: number;
  kind: StorageKind;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  metadata?: Record<string, unknown>;
}): Promise<StorageUploadInitResponse> {
  return apiRequest<StorageUploadInitResponse>("/storage/uploads/init", {
    method: "POST",
    body: JSON.stringify({
      client_id: params.clientId,
      kind: params.kind,
      original_filename: params.fileName,
      mime_type: params.mimeType,
      size_bytes: params.sizeBytes,
      metadata: params.metadata ?? {},
    }),
  });
}

export async function uploadFileToPresignedUrl(params: {
  url: string;
  file: File;
  method?: string;
  headers?: Record<string, string>;
}): Promise<void> {
  const headers = new Headers(params.headers ?? {});
  if (!headers.has("Content-Type")) headers.set("Content-Type", params.file.type || "application/octet-stream");
  const response = await fetch(params.url, {
    method: params.method || "PUT",
    body: params.file,
    headers,
  });
  if (!response.ok) {
    throw new Error(`Upload failed with status ${response.status}`);
  }
}

export async function completeDirectUpload(params: {
  clientId: number;
  mediaId: string;
}): Promise<StorageUploadCompleteResponse> {
  return apiRequest<StorageUploadCompleteResponse>("/storage/uploads/complete", {
    method: "POST",
    body: JSON.stringify({
      client_id: params.clientId,
      media_id: params.mediaId,
    }),
  });
}

export async function getMediaAccessUrl(params: {
  clientId: number;
  mediaId: string;
  disposition?: "inline" | "attachment";
}): Promise<StorageAccessUrlResponse> {
  const query = new URLSearchParams({
    client_id: String(params.clientId),
    disposition: params.disposition || "inline",
  });
  return apiRequest<StorageAccessUrlResponse>(`/storage/media/${encodeURIComponent(params.mediaId)}/access-url?${query.toString()}`);
}
