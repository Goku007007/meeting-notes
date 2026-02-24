"use client";

import { useMemo, useState } from "react";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { DocumentsPanel } from "@/components/documents/DocumentsPanel";
import { VerifyPanel } from "@/components/verify/VerifyPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMeetingDocuments, type MeetingDocument } from "@/lib/queries/documents";
import { getMeetingIndexState, type MeetingIndexState } from "@/lib/state/meetingIndexState";

type MeetingWorkspaceProps = {
  meetingId: string;
  meetingTitle?: string;
  meetingCreatedAt?: string;
};

type MobileTab = "chat" | "verify" | "docs";
const EMPTY_DOCUMENTS: MeetingDocument[] = [];

function IndexingBanner({ state }: { state: MeetingIndexState }) {
  if (state === "NOT_INDEXED") {
    return (
      <Card className="rounded-2xl border-blue-200 bg-blue-50/90 shadow-sm">
        <CardContent className="pt-6 text-sm text-blue-900">
          Indexing in progress. Chat responses may be limited until the first document is indexed.
        </CardContent>
      </Card>
    );
  }
  if (state === "PARTIALLY_INDEXED") {
    return (
      <Card className="rounded-2xl border-amber-200 bg-amber-50/90 shadow-sm">
        <CardContent className="pt-6 text-sm text-amber-900">
          Some documents are still indexing. Results may be incomplete.
        </CardContent>
      </Card>
    );
  }
  if (state === "FAILED_ONLY") {
    return (
      <Card className="rounded-2xl border-red-200 bg-red-50/90 shadow-sm">
        <CardContent className="pt-6 text-sm text-red-900">
          All documents failed indexing. Reindex a failed document from Docs.
        </CardContent>
      </Card>
    );
  }
  if (state === "EMPTY") {
    return (
      <Card className="rounded-2xl border-slate-200/90 bg-white/85 shadow-sm">
        <CardContent className="pt-6 text-sm text-slate-600">
          No documents yet. Attach files in the chat composer to start.
        </CardContent>
      </Card>
    );
  }
  return null;
}

export function MeetingWorkspace({
  meetingId,
  meetingTitle,
  meetingCreatedAt,
}: MeetingWorkspaceProps) {
  const [mobileTab, setMobileTab] = useState<MobileTab>("chat");
  const documentsQuery = useMeetingDocuments(meetingId);
  const documents = documentsQuery.data ?? EMPTY_DOCUMENTS;
  const indexState = useMemo(() => getMeetingIndexState(documents), [documents]);
  const lastUpdatedLabel = useMemo(() => {
    const timestamps = documents
      .flatMap((doc) => [doc.indexed_at, doc.processing_started_at])
      .filter((value): value is string => Boolean(value))
      .map((value) => new Date(value))
      .filter((date) => !Number.isNaN(date.getTime()))
      .sort((a, b) => b.getTime() - a.getTime());
    if (timestamps.length === 0) return "No updates yet";
    return timestamps[0].toLocaleString();
  }, [documents]);

  if (documentsQuery.isLoading) {
    return (
      <main className="space-y-4 p-4 md:p-6">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-[620px] w-full" />
      </main>
    );
  }

  if (documentsQuery.isError) {
    const message =
      documentsQuery.error && typeof documentsQuery.error === "object" && "message" in documentsQuery.error
        ? String(documentsQuery.error.message)
        : "Failed to load meeting documents.";
    return (
      <main className="p-4 md:p-6">
        <Card className="rounded-2xl border-red-200 bg-red-50/90 shadow-sm">
          <CardContent className="pt-6 text-sm text-red-700">{message}</CardContent>
        </Card>
      </main>
    );
  }

  const chatContent = (
    <ChatPanel meetingId={meetingId} documents={documents} indexState={indexState} />
  );
  const verifyContent = <VerifyPanel meetingId={meetingId} indexState={indexState} />;
  const docsContent = <DocumentsPanel meetingId={meetingId} documents={documents} />;
  const createdLabel =
    meetingCreatedAt && !Number.isNaN(new Date(meetingCreatedAt).getTime())
      ? new Date(meetingCreatedAt).toLocaleDateString()
      : "—";

  return (
    <main className="space-y-4 p-4 md:p-6 lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:gap-4 lg:space-y-0 lg:overflow-hidden">
      <Card className="rounded-2xl border-slate-200/90 bg-white/85 py-4 shadow-sm">
        <CardContent className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold tracking-[0.18em] text-emerald-600 uppercase">Meeting Context</p>
            <p className="text-lg font-semibold text-slate-800">{meetingTitle ?? "Meeting"}</p>
          </div>
          <div className="text-xs text-slate-600">
            <p>
              <span className="font-medium text-slate-700">State:</span> {indexState}
            </p>
            <p>
              <span className="font-medium text-slate-700">Created:</span> {createdLabel}
            </p>
            <p>
              <span className="font-medium text-slate-700">Last update:</span> {lastUpdatedLabel}
            </p>
          </div>
        </CardContent>
      </Card>
      <IndexingBanner state={indexState} />

      <section className="space-y-4 lg:hidden">
        <div className="flex flex-wrap gap-2 rounded-2xl border border-slate-200/80 bg-white/80 p-2 shadow-sm">
          <Button
            type="button"
            className={`rounded-xl ${
              mobileTab === "chat"
                ? "bg-emerald-500 text-white hover:bg-emerald-600"
                : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100"
            }`}
            variant={mobileTab === "chat" ? "default" : "outline"}
            onClick={() => setMobileTab("chat")}
          >
            Chat
          </Button>
          <Button
            type="button"
            className={`rounded-xl ${
              mobileTab === "verify"
                ? "bg-emerald-500 text-white hover:bg-emerald-600"
                : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100"
            }`}
            variant={mobileTab === "verify" ? "default" : "outline"}
            onClick={() => setMobileTab("verify")}
          >
            Verify
          </Button>
          <Button
            type="button"
            className={`rounded-xl ${
              mobileTab === "docs"
                ? "bg-emerald-500 text-white hover:bg-emerald-600"
                : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100"
            }`}
            variant={mobileTab === "docs" ? "default" : "outline"}
            onClick={() => setMobileTab("docs")}
          >
            Docs
          </Button>
        </div>

        {mobileTab === "chat" ? chatContent : null}
        {mobileTab === "verify" ? verifyContent : null}
        {mobileTab === "docs" ? docsContent : null}
      </section>

      <section className="hidden lg:block lg:min-h-0 lg:flex-1">{chatContent}</section>
    </main>
  );
}
