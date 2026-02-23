"use client";

import { useMemo, useState } from "react";
import { usePathname } from "next/navigation";

import { ArtifactsRail } from "@/components/shell/ArtifactsRail";
import { MeetingsRail } from "@/components/shell/MeetingsRail";
import { MobileMeetingsDrawer } from "@/components/shell/MobileMeetingsDrawer";
import { TopNav } from "@/components/shell/TopNav";
import { useMeetingDocuments, type MeetingDocument } from "@/lib/queries/documents";
import { useMeeting } from "@/lib/queries/meetings";
import { getMeetingIndexState } from "@/lib/state/meetingIndexState";

type AppShellProps = {
  children: React.ReactNode;
};
const EMPTY_DOCUMENTS: MeetingDocument[] = [];

function getMeetingIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/meetings\/([^/]+)/);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const meetingId = getMeetingIdFromPath(pathname);
  const isMeetingRoute = Boolean(meetingId);

  const meetingQuery = useMeeting(meetingId ?? "");
  const documentsQuery = useMeetingDocuments(meetingId ?? "");
  const documents = documentsQuery.data ?? EMPTY_DOCUMENTS;
  const indexState = useMemo(
    () => (isMeetingRoute ? getMeetingIndexState(documents) : null),
    [documents, isMeetingRoute],
  );

  return (
    <div className="min-h-screen bg-background">
      <TopNav
        isMeetingRoute={isMeetingRoute}
        meetingTitle={meetingQuery.data?.title ?? null}
        indexState={indexState}
        onOpenMeetings={() => setDrawerOpen(true)}
      />

      <div className="mx-auto w-full max-w-[1700px] lg:grid lg:grid-cols-[280px_1fr_380px]">
        <aside className="hidden border-r lg:block">
          <div className="sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto">
            <MeetingsRail activeMeetingId={meetingId} />
          </div>
        </aside>

        <main className="min-h-[calc(100vh-3.5rem)]">{children}</main>

        <aside className="hidden border-l lg:block">
          {meetingId && indexState ? (
            <div className="sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto">
              <ArtifactsRail meetingId={meetingId} documents={documents} indexState={indexState} />
            </div>
          ) : (
            <div className="p-4 text-sm text-muted-foreground">
              Select a meeting to view verify results, tasks, issues, and documents.
            </div>
          )}
        </aside>
      </div>

      <MobileMeetingsDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        activeMeetingId={meetingId}
      />
    </div>
  );
}
