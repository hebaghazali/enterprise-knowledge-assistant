import { apiFetch } from "./api-client";
import type { AnswerSource, Citation } from "./answering-api";
import { postSse, type StreamCallbacks } from "./sse-client";

export interface ConversationCreated {
  conversation_id: string;
  created_at: string;
}

export interface ConversationMessage {
  message_id: string;
  role: "user" | "assistant" | string;
  content: string;
  created_at: string;
}

export interface ConversationDetail {
  conversation_id: string;
  created_at: string;
  messages: ConversationMessage[];
}

export interface SendMessageResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  citations: Citation[];
  sources: AnswerSource[];
}

export function createConversation(): Promise<ConversationCreated> {
  return apiFetch("/conversations", { method: "POST" });
}

export function getConversation(conversationId: string): Promise<ConversationDetail> {
  return apiFetch(`/conversations/${encodeURIComponent(conversationId)}`);
}

export function sendConversationMessage(
  conversationId: string,
  message: string,
  k = 5,
): Promise<SendMessageResponse> {
  return apiFetch(`/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, k }),
  });
}

export function streamConversationMessage(
  conversationId: string,
  message: string,
  k: number,
  signal: AbortSignal,
  callbacks: StreamCallbacks,
): Promise<SendMessageResponse> {
  return postSse(
    `/conversations/${encodeURIComponent(conversationId)}/messages/stream`,
    { message, k },
    signal,
    callbacks,
  );
}
