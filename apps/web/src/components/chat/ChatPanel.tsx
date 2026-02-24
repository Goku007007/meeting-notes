"use client";

import { AlertCircle, Bot, Loader2, Sparkles, User } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { toast } from "sonner";

import { AttachmentChips, type PendingUploadChip } from "@/components/chat/AttachmentChips";
import { CitationDrawer } from "@/components/chat/CitationDrawer";
import { Composer } from "@/components/chat/Composer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useChat,
  useChatHistory,
  type ChatCitation,
  type ChatHistoryTurn,
} from "@/lib/queries/chat";
import { useUploadDocument, type MeetingDocument } from "@/lib/queries/documents";
import type { MeetingIndexState } from "@/lib/state/meetingIndexState";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations: ChatCitation[];
  createdAt: string;
};

type ChatPanelProps = {
  meetingId: string;
  documents: MeetingDocument[];
  indexState: MeetingIndexState;
};

const ACCEPTED_FILE_TYPES =
  ".pdf,.docx,.pptx,.xlsx,.html,.htm,.eml,.txt,.md,.png,.jpg,.jpeg,.webp";

function inferDocType(fileName: string): string {
  const lowered = fileName.toLowerCase();
  if (lowered.endsWith(".eml")) return "email";
  return "notes";
}

function messageClass(role: "user" | "assistant"): string {
  return role === "user"
    ? "ml-auto max-w-[82%] rounded-2xl rounded-br-md bg-primary px-4 py-3 text-sm text-primary-foreground shadow-sm"
    : "mr-auto max-w-[82%] rounded-2xl rounded-bl-md border bg-card px-4 py-3 text-sm shadow-sm";
}

function mapTurnsToMessages(turns: ChatHistoryTurn[]): ChatMessage[] {
  const messages: ChatMessage[] = [];
  for (const turn of turns) {
    messages.push({
      id: `user-${turn.run_id}`,
      role: "user",
      text: turn.question,
      citations: [],
      createdAt: turn.created_at,
    });
    if (turn.answer) {
      messages.push({
        id: `assistant-${turn.run_id}`,
        role: "assistant",
        text: turn.answer,
        citations: turn.citations ?? [],
        createdAt: turn.created_at,
      });
    }
  }
  return messages;
}

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function getDocumentStateSummary(documents: MeetingDocument[]): {
  indexed: number;
  processing: number;
  failed: number;
} {
  return documents.reduce(
    (acc, doc) => {
      if (doc.status === "indexed") acc.indexed += 1;
      if (doc.status === "processing" || doc.status === "pending") acc.processing += 1;
      if (doc.status === "failed") acc.failed += 1;
      return acc;
    },
    { indexed: 0, processing: 0, failed: 0 },
  );
}

export function ChatPanel({ meetingId, documents, indexState }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [pendingUploads, setPendingUploads] = useState<PendingUploadChip[]>([]);
  const [attachedDocumentIds, setAttachedDocumentIds] = useState<string[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<ChatCitation | null>(null);
  const [isUploadingFiles, setIsUploadingFiles] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  const chatMutation = useChat(meetingId);
  const chatHistoryQuery = useChatHistory(meetingId);
  const uploadMutation = useUploadDocument(meetingId);

  const attachedDocuments = useMemo(() => {
    const byId = new Map(documents.map((doc) => [doc.document_id, doc]));
    return attachedDocumentIds
      .map((id) => byId.get(id))
      .filter((doc): doc is MeetingDocument => Boolean(doc));
  }, [attachedDocumentIds, documents]);
  const docSummary = useMemo(() => getDocumentStateSummary(documents), [documents]);

  useEffect(() => {
    if (!chatHistoryQuery.data) return;
    setMessages(mapTurnsToMessages(chatHistoryQuery.data));
  }, [chatHistoryQuery.data, meetingId]);

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
    if (!files.length) return;

    setIsUploadingFiles(true);
    try {
      await Promise.allSettled(files.map((file) => uploadOneFile(file)));
    } finally {
      setIsUploadingFiles(false);
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
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");

    try {
      const response = await chatMutation.mutateAsync(trimmed);
      setMessages((prev) => [
        ...prev,
        {
          id: response.run_id ? `assistant-${response.run_id}` : `assistant-${Date.now()}`,
          role: "assistant",
          text: response.answer,
          citations: response.citations ?? [],
          createdAt: new Date().toISOString(),
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
    <Card className="flex min-h-[680px] flex-col rounded-2xl border bg-gradient-to-b from-background to-muted/10 shadow-sm">
      <CardHeader>
        <CardTitle>Chat</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border bg-muted/20 p-4">
          {chatHistoryQuery.isLoading && messages.length === 0 ? (
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading chat history...
            </div>
          ) : null}
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

          {messages.map((message) => {
            const isUser = message.role === "user";
            return (
              <div
                key={message.id}
                className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-1 duration-300`}
              >
                {!isUser ? (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-background">
                    <Bot className="h-4 w-4 text-muted-foreground" />
                  </div>
                ) : null}
                  <div className={`${messageClass(message.role)} transition-all duration-200`}>
                  <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
                  <p className={`mt-2 text-[11px] ${isUser ? "text-primary-foreground/80" : "text-muted-foreground"}`}>
                    {formatTime(message.createdAt)}
                  </p>
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
                              Cite {index + 1}
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
                {isUser ? (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-primary/10">
                    <User className="h-4 w-4 text-primary" />
                  </div>
                ) : null}
              </div>
            );
          })}

          {chatMutation.isPending ? (
            <div className="flex justify-start gap-3 animate-in fade-in slide-in-from-bottom-1 duration-300">
              <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-background">
                <Bot className="h-4 w-4 text-muted-foreground" />
              </div>
                <div className={`${messageClass("assistant")} transition-all duration-300 ease-out`}>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current [animation-delay:120ms]" />
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current [animation-delay:240ms]" />
                  <span>Thinking...</span>
                </div>
              </div>
            </div>
          ) : null}

          <div ref={scrollAnchorRef} />
        </div>

        <div className="space-y-3 rounded-xl border bg-background p-3 shadow-sm">
          <AttachmentChips
            meetingId={meetingId}
            pendingUploads={pendingUploads}
            attachedDocuments={attachedDocuments}
            onRemovePending={(id) =>
              setPendingUploads((prev) => prev.filter((item) => item.id !== id))
            }
          />

          {indexState === "NOT_INDEXED" ? (
            <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-900 animate-in fade-in duration-300">
              <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>
                <p className="font-medium">Indexing in progress</p>
                <p className="text-blue-800">
                  Attachments are being processed. Chat unlocks automatically once the first file is indexed.
                </p>
              </div>
            </div>
          ) : null}

          {indexState === "PARTIALLY_INDEXED" ? (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 animate-in fade-in duration-300">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>
                <p className="font-medium">Some files still indexing</p>
                <p className="text-amber-800">
                  {docSummary.indexed} ready, {docSummary.processing} processing, {docSummary.failed} failed.
                  Answers may improve as indexing completes.
                </p>
              </div>
            </div>
          ) : null}

          {indexState === "FAILED_ONLY" ? (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-900 animate-in fade-in duration-300">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>
                <p className="font-medium">All current attachments failed</p>
                <p className="text-red-800">
                  Reindex failed files from their chips or attach a new document to continue.
                </p>
              </div>
            </div>
          ) : null}

          {isUploadingFiles ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs text-sky-900">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Uploading attachments...
            </div>
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
            isUploading={isUploadingFiles}
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
