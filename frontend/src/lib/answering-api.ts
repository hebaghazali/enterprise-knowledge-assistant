import { apiFetch } from "./api-client";

export interface AnswerSource {
  chunk_id: string;
  document_id: string;
  filename: string;
  chunk_index: number;
  similarity_score: number;
  content_preview: string;
}

export interface Citation extends AnswerSource {
  source_number: number;
}

export interface AnswerResponse {
  question: string;
  answer: string;
  citations: Citation[];
  sources: AnswerSource[];
  model: string;
  k: number;
}

export function askQuestion(question: string, k = 5): Promise<AnswerResponse> {
  return apiFetch("/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, k }),
  });
}
