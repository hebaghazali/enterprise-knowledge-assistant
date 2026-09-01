export type DocStatus =
  | "Uploaded"
  | "Queued"
  | "Processing"
  | "Chunked"
  | "Vector Indexed"
  | "Failed";

export interface Document {
  id: string;
  name: string;
  type: "PDF" | "TXT" | "MD";
  status: DocStatus;
  chunks: number;
  createdAt: string;
}
