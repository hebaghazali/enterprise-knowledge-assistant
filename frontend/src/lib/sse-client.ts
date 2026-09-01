import { API_BASE, ApiError } from "./api-client";

export interface StreamCallbacks {
  onSources?: (data: Record<string, unknown>) => void;
  onToken?: (text: string) => void;
}

export async function postSse<T>(
  path: string,
  body: unknown,
  signal: AbortSignal,
  callbacks: StreamCallbacks,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = payload?.detail;
    throw new ApiError(
      response.status,
      typeof detail === "string" ? detail : `HTTP ${response.status}`,
      detail,
    );
  }
  if (!response.body) throw new Error("Streaming is not supported by this browser.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: T | undefined;

  const consume = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) return;
    const data = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
    if (event === "sources") callbacks.onSources?.(data);
    if (event === "token") callbacks.onToken?.(String(data.text ?? ""));
    if (event === "error") throw new Error(String(data.detail ?? "Generation failed."));
    if (event === "complete") completed = data as T;
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    blocks.forEach(consume);
    if (done) break;
  }
  if (buffer.trim()) consume(buffer);
  if (!completed) throw new Error("The stream ended before completion.");
  return completed;
}
