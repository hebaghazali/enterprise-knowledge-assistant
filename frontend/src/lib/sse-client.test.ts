import { describe, expect, it, vi } from "vitest";

import { postSse } from "./sse-client";

function streamResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } },
  );
}

describe("postSse", () => {
  it("assembles split SSE frames and returns completion data", async () => {
    const onToken = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          streamResponse([
            'event: token\ndata: {"text":"Hel',
            'lo"}\n\nevent: complete\ndata: {"answer":"Hello"}\n\n',
          ]),
        ),
    );

    const result = await postSse<{ answer: string }>(
      "/answer/stream",
      { question: "hello" },
      new AbortController().signal,
      { onToken },
    );

    expect(onToken).toHaveBeenCalledWith("Hello");
    expect(result).toEqual({ answer: "Hello" });
    vi.unstubAllGlobals();
  });

  it("surfaces server error events", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          streamResponse(['event: error\ndata: {"detail":"Ollama is offline"}\n\n']),
        ),
    );

    await expect(postSse("/answer/stream", {}, new AbortController().signal, {})).rejects.toThrow(
      "Ollama is offline",
    );
    vi.unstubAllGlobals();
  });
});
