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
};

type MobileTab = "chat" | "verify" | "docs";
const EMPTY_DOCUMENTS: MeetingDocument[] = [];

function IndexingBanner({ state }: { state: MeetingIndexState }) {
  if (state === "NOT_INDEXED") {
    return (
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-6 text-sm text-blue-800">
          Indexing in progress. Chat responses may be limited until the first document is indexed.
        </CardContent>
      </Card>
    );
  }
  if (state === "PARTIALLY_INDEXED") {
    return (
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="pt-6 text-sm text-amber-800">
          Some documents are still indexing. Results may be incomplete.
        </CardContent>
      </Card>
    );
  }
  if (state === "FAILED_ONLY") {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="pt-6 text-sm text-red-800">
          All documents failed indexing. Reindex a failed document from Docs.
        </CardContent>
      </Card>
    );
  }
  if (state === "EMPTY") {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          No documents yet. Attach files in the chat composer to start.
        </CardContent>
      </Card>
    );
  }
  return null;
}

export function MeetingWorkspace({ meetingId }: MeetingWorkspaceProps) {
  const [mobileTab, setMobileTab] = useState<MobileTab>("chat");
  const documentsQuery = useMeetingDocuments(meetingId);
  const documents = documentsQuery.data ?? EMPTY_DOCUMENTS;
  const indexState = useMemo(() => getMeetingIndexState(documents), [documents]);

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
        <Card className="border-red-200">
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

  return (
    <main className="space-y-4 p-4 md:p-6">
      <IndexingBanner state={indexState} />

      <section className="space-y-4 lg:hidden">
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant={mobileTab === "chat" ? "default" : "outline"}
            onClick={() => setMobileTab("chat")}
          >
            Chat
          </Button>
          <Button
            type="button"
            variant={mobileTab === "verify" ? "default" : "outline"}
            onClick={() => setMobileTab("verify")}
          >
            Verify
          </Button>
          <Button
            type="button"
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

      <section className="hidden lg:block">{chatContent}</section>
    </main>
  );
}
