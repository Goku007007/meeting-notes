"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { toast } from "sonner";

import { AttachmentChips, type PendingUploadChip } from "@/components/chat/AttachmentChips";
import { CitationDrawer } from "@/components/chat/CitationDrawer";
import { Composer } from "@/components/chat/Composer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useChat, type ChatCitation } from "@/lib/queries/chat";
import { useUploadDocument, type MeetingDocument } from "@/lib/queries/documents";
import type { MeetingIndexState } from "@/lib/state/meetingIndexState";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations: ChatCitation[];
};

type ChatPanelProps = {
  meetingId: string;
  documents: MeetingDocument[];
  indexState: MeetingIndexState;
};

const ACCEPTED_FILE_TYPES =
  ".pdf,.docx,.pptx,.xlsx,.html,.htm,.eml,.txt,.md,.png,.jpg,.jpeg,.webp";
const MAX_STORED_MESSAGES = 100;

function chatStorageKey(meetingId: string): string {
  return `meeting-chat-history:${meetingId}`;
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") return false;
  const maybe = value as Partial<ChatMessage>;
  if (typeof maybe.id !== "string") return false;
  if (maybe.role !== "user" && maybe.role !== "assistant") return false;
  if (typeof maybe.text !== "string") return false;
  if (!Array.isArray(maybe.citations)) return false;
  return maybe.citations.every(
    (citation) =>
      citation &&
      typeof citation === "object" &&
      "chunk_id" in citation &&
      "quote" in citation &&
      typeof citation.chunk_id === "string" &&
      typeof citation.quote === "string",
  );
}

function inferDocType(fileName: string): string {
  const lowered = fileName.toLowerCase();
  if (lowered.endsWith(".eml")) return "email";
  return "notes";
}

function messageClass(role: "user" | "assistant"): string {
  return role === "user"
    ? "ml-auto max-w-[85%] rounded-xl bg-primary px-4 py-3 text-sm text-primary-foreground"
    : "mr-auto max-w-[85%] rounded-xl border bg-card px-4 py-3 text-sm";
}

export function ChatPanel({ meetingId, documents, indexState }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isHistoryHydrated, setIsHistoryHydrated] = useState(false);
  const [question, setQuestion] = useState("");
  const [pendingUploads, setPendingUploads] = useState<PendingUploadChip[]>([]);
  const [attachedDocumentIds, setAttachedDocumentIds] = useState<string[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<ChatCitation | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  const chatMutation = useChat(meetingId);
  const uploadMutation = useUploadDocument(meetingId);

  const attachedDocuments = useMemo(() => {
    const byId = new Map(documents.map((doc) => [doc.document_id, doc]));
    return attachedDocumentIds
      .map((id) => byId.get(id))
      .filter((doc): doc is MeetingDocument => Boolean(doc));
  }, [attachedDocumentIds, documents]);

  useEffect(() => {
    setIsHistoryHydrated(false);
    try {
      const raw = window.localStorage.getItem(chatStorageKey(meetingId));
      if (!raw) {
        setMessages([]);
        setIsHistoryHydrated(true);
        return;
      }
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        setMessages([]);
        setIsHistoryHydrated(true);
        return;
      }
      const hydrated = parsed.filter(isChatMessage).slice(-MAX_STORED_MESSAGES);
      setMessages(hydrated);
    } catch {
      setMessages([]);
    } finally {
      setIsHistoryHydrated(true);
    }
  }, [meetingId]);

  useEffect(() => {
    if (!isHistoryHydrated) return;
    try {
      window.localStorage.setItem(
        chatStorageKey(meetingId),
        JSON.stringify(messages.slice(-MAX_STORED_MESSAGES)),
      );
    } catch {
      // Non-blocking: storage may be unavailable in some private contexts.
    }
  }, [isHistoryHydrated, meetingId, messages]);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, chatMutation.isPending]);

  async function uploadOneFile(file: File): Promise<void> {
    const pendingId = `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const uploadId = `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setPendingUploads((prev) => [...prev, { id: pendingId, name: file.name, status: "uploading", error: null }]);

    try {
      const result = await uploadMutation.mutateAsync({
        doc_type: inferDocType(file.name),
        file,
        upload_id: uploadId,
      });
      const first = Array.isArray(result) ? result[0] : result;
      if (!first?.document_id) {
        throw new Error("Upload did not return a document_id.");
      }
      setPendingUploads((prev) => prev.filter((item) => item.id !== pendingId));
      setAttachedDocumentIds((prev) =>
        prev.includes(first.document_id) ? prev : [first.document_id, ...prev],
      );
    } catch (err) {
      const message =
        err && typeof err === "object" && "message" in err
          ? String(err.message)
          : "Attachment upload failed.";
      setPendingUploads((prev) =>
        prev.map((item) =>
          item.id === pendingId ? { ...item, status: "failed", error: message } : item,
        ),
      );
      toast.error(message);
    }
  }

  async function onAttachFiles(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    for (const file of files) {
      await uploadOneFile(file);
    }
  }

  async function onSendMessage(): Promise<void> {
    const trimmed = question.trim();
    if (!trimmed || chatMutation.isPending || indexState === "NOT_INDEXED") return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: trimmed,
      citations: [],
    };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");

    try {
      const response = await chatMutation.mutateAsync(trimmed);
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          text: response.answer,
          citations: response.citations ?? [],
        },
      ]);
    } catch (err) {
      const message =
        err && typeof err === "object" && "message" in err
          ? String(err.message)
          : "Chat request failed.";
      toast.error(message);
    }
  }

  return (
    <Card className="flex min-h-[680px] flex-col">
      <CardHeader>
        <CardTitle>Chat</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="flex-1 space-y-4 overflow-y-auto rounded-md border p-4">
          {messages.length === 0 ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Suggested questions</p>
              <div className="flex flex-wrap gap-2">
                {[
                  "What did we decide?",
                  "What are action items and owners?",
                  "What's still unclear?",
                ].map((suggestion) => (
                  <Button
                    key={suggestion}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setQuestion(suggestion)}
                  >
                    {suggestion}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`${messageClass(message.role)} transition-all duration-300 ease-out`}
            >
              <p className="whitespace-pre-wrap">{message.text}</p>
              {message.role === "assistant" ? (
                <div className="mt-3 space-y-2">
                  {message.citations.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {message.citations.map((citation, index) => (
                        <Button
                          key={`${message.id}-${citation.chunk_id}-${index}`}
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setSelectedCitation(citation)}
                        >
                          {citation.chunk_id.slice(0, 8)}
                        </Button>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      No citations available. This answer may be unsupported.
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          ))}

          {chatMutation.isPending ? (
            <div className={`${messageClass("assistant")} transition-all duration-300 ease-out`}>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current [animation-delay:120ms]" />
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current [animation-delay:240ms]" />
                <span>Thinking...</span>
              </div>
            </div>
          ) : null}

          <div ref={scrollAnchorRef} />
        </div>

        <div className="space-y-3 rounded-md border p-3">
          <AttachmentChips
            meetingId={meetingId}
            pendingUploads={pendingUploads}
            attachedDocuments={attachedDocuments}
            onRemovePending={(id) =>
              setPendingUploads((prev) => prev.filter((item) => item.id !== id))
            }
          />

          {indexState === "NOT_INDEXED" ? (
            <p className="text-xs text-blue-700">
              Indexing in progress. Attachments are uploading, chat will enable once first document is indexed.
            </p>
          ) : null}

          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            multiple
            accept={ACCEPTED_FILE_TYPES}
            onChange={(event) => {
              void onAttachFiles(event);
            }}
          />

          <Composer
            question={question}
            disabled={indexState === "NOT_INDEXED"}
            isSending={chatMutation.isPending}
            onQuestionChange={setQuestion}
            onSend={() => {
              void onSendMessage();
            }}
            onAttachClick={() => fileInputRef.current?.click()}
          />
        </div>
      </CardContent>

      <CitationDrawer
        citation={selectedCitation}
        onOpenChange={(open) => {
          if (!open) setSelectedCitation(null);
        }}
      />
    </Card>
  );
}
