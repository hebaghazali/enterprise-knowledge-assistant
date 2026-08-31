import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertCircle, FileText, Hash, MessageSquarePlus, Send, Sparkles } from "lucide-react";
import { askQuestion, type AnswerResponse, type AnswerSource } from "@/lib/answering-api";
import { ApiError } from "@/lib/api-client";
import {
  createConversation,
  getConversation,
  sendConversationMessage,
  type SendMessageResponse,
} from "@/lib/conversations-api";

export const Route = createFileRoute("/ask")({
  head: () => ({ meta: [{ title: "Ask — Enterprise Knowledge Assistant" }] }),
  component: AskPage,
});

const STORAGE_KEY = "eka.active-conversation.v1";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const suggestions = [
  "What is our paid time off policy?",
  "Summarize the indexed knowledge base.",
  "How do I onboard a new engineer?",
  "What are the data retention rules?",
];

function TopK({
  value,
  onChange,
  disabled = false,
}: {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted-foreground">
      Sources
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground disabled:opacity-60"
      >
        {Array.from({ length: 10 }, (_, index) => index + 1).map((item) => (
          <option key={item}>{item}</option>
        ))}
      </select>
    </label>
  );
}

function SourceList({ sources }: { sources: AnswerSource[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs uppercase tracking-widest text-muted-foreground">
        Retrieved sources
      </div>
      {sources.map((source) => (
        <div key={source.chunk_id} className="rounded-lg border border-border bg-background/40 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="flex min-w-0 items-center gap-2 font-medium">
              <FileText className="h-3.5 w-3.5 text-primary" />{" "}
              <span className="truncate">{source.filename}</span>
            </span>
            <span className="flex items-center gap-2 text-muted-foreground">
              <Hash className="h-3 w-3" />
              {source.chunk_index} · {source.similarity_score.toFixed(3)}
            </span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            {source.content_preview}
          </p>
        </div>
      ))}
    </div>
  );
}

function AnswerCard({ answer }: { answer: AnswerResponse }) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>
            Model: <code className="text-primary">{answer.model}</code>
          </span>
          <span>Top-k: {answer.k}</span>
          <span>{answer.citations.length} citations</span>
        </div>
        <p className="mt-4 whitespace-pre-wrap text-[15px] leading-relaxed">{answer.answer}</p>
        {answer.citations.length > 0 && (
          <div className="mt-5 space-y-2">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Citations</div>
            {answer.citations.map((citation) => (
              <div
                key={`${citation.source_number}-${citation.chunk_id}`}
                className="rounded-lg border border-border bg-background/40 p-3 text-sm"
              >
                <span className="font-medium">
                  [{citation.source_number}] {citation.filename}
                </span>
                <span className="ml-2 text-xs text-muted-foreground">
                  chunk {citation.chunk_index}
                </span>
                <p className="mt-1 text-sm text-muted-foreground">{citation.content_preview}</p>
              </div>
            ))}
          </div>
        )}
      </div>
      <aside className="h-fit rounded-xl border border-border bg-card p-5 lg:sticky lg:top-6">
        <SourceList sources={answer.sources} />
      </aside>
    </div>
  );
}

function AskPage() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState("quick");
  const [quickQuestion, setQuickQuestion] = useState("");
  const [chatMessage, setChatMessage] = useState("");
  const [k, setK] = useState(5);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [storageRestored, setStorageRestored] = useState(false);
  const [latestChatAnswer, setLatestChatAnswer] = useState<SendMessageResponse | null>(null);
  const conversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && UUID_PATTERN.test(stored)) {
      conversationIdRef.current = stored;
      setConversationId(stored);
    } else if (stored) {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    setStorageRestored(true);
  }, []);

  const conversation = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => getConversation(conversationId!),
    enabled: mode === "chat" && storageRestored && Boolean(conversationId),
    retry: 1,
  });

  useEffect(() => {
    if (
      conversation.error instanceof ApiError &&
      (conversation.error.status === 404 || conversation.error.status === 422)
    ) {
      window.localStorage.removeItem(STORAGE_KEY);
      conversationIdRef.current = null;
      setConversationId(null);
    }
  }, [conversation.error]);

  const quickAnswer = useMutation({
    mutationFn: ({ question, k }: { question: string; k: number }) => askQuestion(question, k),
  });

  const chatSend = useMutation({
    mutationFn: async ({ message, k }: { message: string; k: number }) => {
      let id = conversationIdRef.current;
      if (!id) {
        const created = await createConversation();
        id = created.conversation_id;
        conversationIdRef.current = id;
        setConversationId(id);
        window.localStorage.setItem(STORAGE_KEY, id);
      }
      const response = await sendConversationMessage(id, message, k);
      return { id, response };
    },
    onSuccess: ({ response }) => {
      setLatestChatAnswer(response);
      setChatMessage("");
    },
    onSettled: async (data) => {
      const id = data?.id ?? conversationIdRef.current;
      if (id) await queryClient.invalidateQueries({ queryKey: ["conversation", id] });
    },
  });

  const submitQuick = (text?: string) => {
    const question = (text ?? quickQuestion).trim();
    if (!question) return;
    setQuickQuestion(question);
    quickAnswer.mutate({ question, k });
  };

  const submitChat = () => {
    const message = chatMessage.trim();
    if (message) chatSend.mutate({ message, k });
  };

  const newChat = () => {
    if (conversationId) queryClient.removeQueries({ queryKey: ["conversation", conversationId] });
    window.localStorage.removeItem(STORAGE_KEY);
    conversationIdRef.current = null;
    setConversationId(null);
    setLatestChatAnswer(null);
    setChatMessage("");
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Retrieval-Augmented Generation"
        title="Ask your knowledge base"
        description="Use a single grounded answer or continue a history-aware conversation."
      />
      <div className="mx-auto max-w-6xl px-6 py-8">
        <Tabs value={mode} onValueChange={setMode}>
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <TabsList>
              <TabsTrigger value="quick">Quick Answer</TabsTrigger>
              <TabsTrigger value="chat">Chat</TabsTrigger>
            </TabsList>
            <TopK
              value={k}
              onChange={setK}
              disabled={quickAnswer.isPending || chatSend.isPending}
            />
          </div>

          <TabsContent value="quick" className="space-y-6">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                submitQuick();
              }}
              className="flex items-center gap-2 rounded-xl border border-border bg-card p-2"
            >
              <Sparkles className="ml-3 h-4 w-4 text-primary" />
              <input
                value={quickQuestion}
                onChange={(event) => setQuickQuestion(event.target.value)}
                placeholder="Ask a question about your knowledge base…"
                className="min-w-0 flex-1 bg-transparent py-2 outline-none placeholder:text-muted-foreground"
              />
              <Button type="submit" disabled={!quickQuestion.trim() || quickAnswer.isPending}>
                <Send /> {quickAnswer.isPending ? "Thinking…" : "Ask"}
              </Button>
            </form>
            {!quickAnswer.data && !quickAnswer.isPending && (
              <div className="flex flex-wrap gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => submitQuick(suggestion)}
                    className="rounded-full border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            {quickAnswer.isError && <ErrorMessage error={quickAnswer.error} />}
            {quickAnswer.data && <AnswerCard answer={quickAnswer.data} />}
          </TabsContent>

          <TabsContent value="chat" className="space-y-4">
            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={newChat} disabled={chatSend.isPending}>
                <MessageSquarePlus /> New chat
              </Button>
            </div>
            <div className="min-h-80 space-y-3 rounded-xl border border-border bg-card p-5">
              {conversation.isPending && conversationId && (
                <div className="text-sm text-muted-foreground">Restoring conversation…</div>
              )}
              {!conversationId && !chatSend.isPending && (
                <div className="py-20 text-center text-sm text-muted-foreground">
                  Send a message to start a new conversation.
                </div>
              )}
              {conversation.data?.messages.map((message) => (
                <div
                  key={message.message_id}
                  className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={
                      message.role === "user"
                        ? "max-w-[85%] rounded-xl bg-primary px-4 py-3 text-sm text-primary-foreground"
                        : "max-w-[85%] rounded-xl border border-border bg-background/50 px-4 py-3 text-sm"
                    }
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                    {message.role === "assistant" &&
                      latestChatAnswer?.message_id === message.message_id && (
                        <div className="mt-4 space-y-3 border-t border-border pt-3">
                          {latestChatAnswer.citations.length > 0 && (
                            <div className="text-xs text-muted-foreground">
                              Citations:{" "}
                              {latestChatAnswer.citations
                                .map(
                                  (citation) =>
                                    `[${citation.source_number}] ${citation.filename} #${citation.chunk_index}`,
                                )
                                .join(" · ")}
                            </div>
                          )}
                          <SourceList sources={latestChatAnswer.sources} />
                        </div>
                      )}
                  </div>
                </div>
              ))}
              {chatSend.isPending && chatSend.variables && (
                <>
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-xl bg-primary px-4 py-3 text-sm text-primary-foreground">
                      {chatSend.variables.message}
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="rounded-xl border border-border bg-background/50 px-4 py-3 text-sm text-muted-foreground">
                      Generating a grounded answer…
                    </div>
                  </div>
                </>
              )}
            </div>
            {conversation.isError && conversationId && <ErrorMessage error={conversation.error} />}
            {chatSend.isError && <ErrorMessage error={chatSend.error} />}
            <form
              onSubmit={(event) => {
                event.preventDefault();
                submitChat();
              }}
              className="flex items-center gap-2 rounded-xl border border-border bg-card p-2"
            >
              <input
                value={chatMessage}
                onChange={(event) => setChatMessage(event.target.value)}
                placeholder="Continue the conversation…"
                className="min-w-0 flex-1 bg-transparent px-3 py-2 outline-none placeholder:text-muted-foreground"
              />
              <Button type="submit" disabled={!chatMessage.trim() || chatSend.isPending}>
                <Send /> Send
              </Button>
            </form>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}

function ErrorMessage({ error }: { error: unknown }) {
  return (
    <div className="flex items-start gap-2 rounded-xl border border-[var(--color-destructive)]/30 p-4 text-sm text-[var(--color-destructive)]">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      {error instanceof Error ? error.message : "The request failed."}
    </div>
  );
}
