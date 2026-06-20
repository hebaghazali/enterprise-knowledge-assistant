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
interface BackendDocResponse extends BackendDocListItem {
  content_type: string | null;
  source_type: string;
  metadata: Record<string, unknown> | null;
  updated_at: string;
  text_length: number | null;
}

const STATUS_MAP: Record<string, DocStatus> = {
  uploaded: "Uploaded",
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
  const raw = await apiFetch<BackendDocResponse>("/documents/upload", {
    method: "POST",
    body: form,
  });
  return toDocument(raw);
}
