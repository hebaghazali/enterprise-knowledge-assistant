import { ApiError, apiFetch } from "./api-client";

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  filename: string;
  chunk_index: number;
  content: string;
  token_count: number | null;
  similarity_score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  result_count: number;
}

export async function searchKnowledge(query: string, k = 5): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, k: String(k) });
  try {
    return await apiFetch(`/search?${params}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { query, results: [], result_count: 0 };
    }
    throw error;
  }
}
