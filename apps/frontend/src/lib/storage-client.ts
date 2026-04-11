import { apiRequest, API_BASE_URL, ApiRequestError, getAuthToken } from "@/lib/api";

export type StorageKind = "image" | "video" | "document" | "audio" | "other";
export type StorageMediaSort =
  | "newest"
  | "oldest"
  | "name_asc"
  | "name_desc"
  | "size_asc"
  | "size_desc";
export type StorageMediaSource = "user_upload" | "backend_ingest" | "platform_sync" | "enriched_catalog";

export type StorageMediaListItem = {
  media_id: string;
  client_id: number;
  kind: StorageKind | string;
  source: StorageMediaSource | string;
  status: string;
  original_filename: string;
  display_name: string;
  folder_id: string | null;
  mime_type: string;
  size_bytes?: number | null;
  created_at?: string | null;
  uploaded_at?: string | null;
};

export type StorageMediaListResponse = {
  items: StorageMediaListItem[];
  limit: number;
  offset: number;
  total: number;
};

export type StorageFolder = {
  folder_id: string;
  client_id: number;
  parent_folder_id: string | null;
  name: string;
  system: boolean;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
};

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
  folderId?: string | null;
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
      folder_id: params.folderId ?? null,
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

export async function uploadFileViaBackend(params: {
  clientId: number;
  kind: StorageKind;
  file: File;
  folderId?: string | null;
}): Promise<StorageUploadCompleteResponse> {
  // Backend-proxied upload: the file body goes through the FastAPI server,
  // which then PUTs it to S3 using boto3. Use this as a fallback when the
  // browser-direct PUT to the S3 presigned URL fails (typically due to CORS
  // or a mixed-content block on the bucket's domain).
  const token = getAuthToken();
  if (!token) throw new ApiRequestError("Authentication required", 401);

  const formData = new FormData();
  formData.append("client_id", String(params.clientId));
  formData.append("kind", params.kind);
  if (params.folderId) formData.append("folder_id", params.folderId);
  formData.append("file", params.file);

  const response = await fetch(`${API_BASE_URL}/storage/uploads/binary`, {
    method: "POST",
    body: formData,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiRequestError(detail || `Upload failed with status ${response.status}`, response.status);
  }
  return (await response.json()) as StorageUploadCompleteResponse;
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

export async function listMedia(params: {
  clientId: number;
  folderId?: string | null; // "root" for top-level files
  kind?: StorageKind;
  search?: string;
  sort?: StorageMediaSort;
  limit?: number;
  offset?: number;
}): Promise<StorageMediaListResponse> {
  const query = new URLSearchParams();
  query.set("client_id", String(params.clientId));
  if (params.folderId !== undefined && params.folderId !== null && params.folderId !== "") {
    query.set("folder_id", params.folderId);
  }
  if (params.kind) query.set("kind", params.kind);
  if (params.search && params.search.trim() !== "") query.set("search", params.search.trim());
  if (params.sort) query.set("sort", params.sort);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  return apiRequest<StorageMediaListResponse>(`/storage/media?${query.toString()}`);
}

export async function updateMedia(params: {
  clientId: number;
  mediaId: string;
  displayName?: string;
  folderId?: string | null;
  clearFolder?: boolean;
}): Promise<StorageMediaListItem> {
  return apiRequest<StorageMediaListItem>(`/storage/media/${encodeURIComponent(params.mediaId)}`, {
    method: "PATCH",
    body: JSON.stringify({
      client_id: params.clientId,
      display_name: params.displayName,
      folder_id: params.folderId ?? null,
      clear_folder: params.clearFolder ?? false,
    }),
  });
}

export async function deleteMedia(params: {
  clientId: number;
  mediaId: string;
}): Promise<void> {
  const query = new URLSearchParams({ client_id: String(params.clientId) });
  await apiRequest<unknown>(`/storage/media/${encodeURIComponent(params.mediaId)}?${query.toString()}`, {
    method: "DELETE",
  });
}

// ── Folders ───────────────────────────────────────────────────────────────

export async function listFolders(params: {
  clientId: number;
  parentFolderId?: string | null;
}): Promise<{ items: StorageFolder[] }> {
  const query = new URLSearchParams({ client_id: String(params.clientId) });
  if (params.parentFolderId) query.set("parent_folder_id", params.parentFolderId);
  return apiRequest<{ items: StorageFolder[] }>(`/storage/folders?${query.toString()}`);
}

export async function createFolder(params: {
  clientId: number;
  name: string;
  parentFolderId?: string | null;
}): Promise<StorageFolder> {
  return apiRequest<StorageFolder>("/storage/folders", {
    method: "POST",
    body: JSON.stringify({
      client_id: params.clientId,
      name: params.name,
      parent_folder_id: params.parentFolderId ?? null,
    }),
  });
}

export async function renameFolder(params: {
  clientId: number;
  folderId: string;
  name: string;
}): Promise<StorageFolder> {
  return apiRequest<StorageFolder>(`/storage/folders/${encodeURIComponent(params.folderId)}/rename`, {
    method: "PATCH",
    body: JSON.stringify({ client_id: params.clientId, name: params.name }),
  });
}

export async function moveFolder(params: {
  clientId: number;
  folderId: string;
  parentFolderId: string | null;
}): Promise<StorageFolder> {
  return apiRequest<StorageFolder>(`/storage/folders/${encodeURIComponent(params.folderId)}/move`, {
    method: "PATCH",
    body: JSON.stringify({
      client_id: params.clientId,
      parent_folder_id: params.parentFolderId ?? null,
    }),
  });
}

export async function deleteFolder(params: {
  clientId: number;
  folderId: string;
}): Promise<void> {
  const query = new URLSearchParams({ client_id: String(params.clientId) });
  await apiRequest<unknown>(`/storage/folders/${encodeURIComponent(params.folderId)}?${query.toString()}`, {
    method: "DELETE",
  });
}

// ── Summary ───────────────────────────────────────────────────────────────

export type StorageMediaSummary = {
  client_id: number;
  total_files: number;
  total_bytes: number;
};

export async function getMediaSummary(params: { clientId: number }): Promise<StorageMediaSummary> {
  const query = new URLSearchParams({ client_id: String(params.clientId) });
  return apiRequest<StorageMediaSummary>(`/storage/media-summary?${query.toString()}`);
}
