import { apiFetch } from "./api-client";
import type { Document, DocStatus } from "@/types/document";

// Shapes returned by the backend — only the fields we consume.
interface BackendDocListItem {
  id: string;
  filename: string;
  status: string;
  chunk_count: number;
  created_at: string;
}

// POST /documents/upload returns the full document response.
export interface DocumentDetailsResponse extends BackendDocListItem {
  content_type: string | null;
  source_type: string;
  metadata: Record<string, unknown> | null;
  updated_at: string;
  text_length: number | null;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content_preview: string;
  token_count: number | null;
}

export interface DocumentChunksResponse {
  document_id: string;
  chunk_count: number;
  chunks: DocumentChunk[];
}

export interface ChunkingSummary {
  document_id: string;
  status: "chunked";
  chunk_count: number;
  chunk_size: number;
  chunk_overlap: number;
}

export interface IndexingSummary {
  document_id: string;
  status: "vector_indexed";
  chunk_count: number;
  indexed_chunk_count: number;
  skipped_chunk_count: number;
  embedding_model: string;
  chroma_collection: string;
}

export interface JobAccepted {
  job_id: string;
  document_id: string;
  status: string;
}

export interface IngestionJob extends JobAccepted {
  predecessor_job_id: string | null;
  job_type: string;
  current_stage: string | null;
  progress_current: number;
  progress_total: number;
  attempt_count: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

const STATUS_MAP: Record<string, DocStatus> = {
  uploaded: "Uploaded",
  queued: "Queued",
  processing: "Processing",
  chunked: "Chunked",
  vector_indexed: "Vector Indexed",
  failed: "Failed",
};

function extToType(filename: string): Document["type"] {
  const ext = filename.split(".").pop()?.toUpperCase();
  if (ext === "PDF" || ext === "TXT" || ext === "MD") return ext;
  return "TXT";
}

function toDocument(raw: BackendDocListItem): Document {
  return {
    id: raw.id,
    name: raw.filename,
    type: extToType(raw.filename),
    status: STATUS_MAP[raw.status] ?? "Failed",
    chunks: raw.chunk_count,
    createdAt: raw.created_at.slice(0, 10),
  };
}

export async function listDocuments(): Promise<Document[]> {
  const raw = await apiFetch<BackendDocListItem[]>("/documents");
  return raw.map(toDocument);
}

export async function uploadDocument(file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  const raw = await apiFetch<DocumentDetailsResponse>("/documents/upload", {
    method: "POST",
    body: form,
  });
  return toDocument(raw);
}

export function getDocument(documentId: string): Promise<DocumentDetailsResponse> {
  return apiFetch(`/documents/${encodeURIComponent(documentId)}`);
}

export function getDocumentChunks(documentId: string): Promise<DocumentChunksResponse> {
  return apiFetch(`/documents/${encodeURIComponent(documentId)}/chunks`);
}

export function chunkDocument(
  documentId: string,
  chunkSize = 500,
  chunkOverlap = 50,
): Promise<ChunkingSummary> {
  const params = new URLSearchParams({
    chunk_size: String(chunkSize),
    chunk_overlap: String(chunkOverlap),
  });
  return apiFetch(`/documents/${encodeURIComponent(documentId)}/chunk?${params}`, {
    method: "POST",
  });
}

export function indexDocument(documentId: string): Promise<IndexingSummary> {
  return apiFetch(`/documents/${encodeURIComponent(documentId)}/index`, {
    method: "POST",
  });
}

export function deleteDocument(documentId: string): Promise<void> {
  return apiFetch(`/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
}

export function processDocument(documentId: string): Promise<JobAccepted> {
  return apiFetch(`/documents/${encodeURIComponent(documentId)}/process`, { method: "POST" });
}

export function listDocumentJobs(documentId: string): Promise<IngestionJob[]> {
  return apiFetch(`/documents/${encodeURIComponent(documentId)}/jobs`);
}

export function retryIngestionJob(jobId: string): Promise<JobAccepted> {
  return apiFetch(`/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
}
