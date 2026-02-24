"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ArtifactsRail } from "@/components/shell/ArtifactsRail";
import { MeetingsRail } from "@/components/shell/MeetingsRail";
import { MobileMeetingsDrawer } from "@/components/shell/MobileMeetingsDrawer";
import { TopNav } from "@/components/shell/TopNav";
import { Button } from "@/components/ui/button";
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
    <div className="relative h-screen overflow-hidden bg-[#f2f7f7] text-slate-900">
      <div className="pointer-events-none absolute -left-20 top-[28rem] h-64 w-64 rounded-full bg-emerald-200/25" />
      <div className="pointer-events-none absolute -right-16 top-[24rem] h-52 w-52 rounded-full bg-emerald-100/50" />
      <TopNav
        isMeetingRoute={isMeetingRoute}
        meetingTitle={meetingQuery.data?.title ?? null}
        indexState={indexState}
        onOpenMeetings={() => setDrawerOpen(true)}
      />

      <div className="relative mx-auto h-[calc(100vh-3.5rem)] w-full max-w-[1700px] lg:grid lg:grid-cols-[300px_1fr_390px] lg:overflow-hidden">
        <aside className="hidden border-r border-slate-200/80 bg-white/50 lg:block">
          <div className="h-full overflow-y-auto overscroll-contain">
            <MeetingsRail activeMeetingId={meetingId} />
          </div>
        </aside>

        <main className="h-full overflow-y-auto overscroll-y-contain lg:overflow-hidden">{children}</main>

        <aside className="hidden border-l border-slate-200/80 bg-white/45 lg:block">
          {meetingId && indexState ? (
            <div className="h-full overflow-y-auto overscroll-contain">
              <ArtifactsRail meetingId={meetingId} documents={documents} indexState={indexState} />
            </div>
          ) : (
            <div className="p-4">
              <div className="space-y-3 rounded-2xl border border-slate-200/90 bg-white/85 p-4 text-sm text-slate-600 shadow-sm">
                <p>Select a meeting to view verify results, tasks, issues, and documents.</p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    asChild
                    size="sm"
                    className="rounded-xl bg-emerald-500 text-white hover:bg-emerald-600"
                  >
                    <Link href="/workspace">Open Workspace</Link>
                  </Button>
                  <Button size="sm" variant="outline" className="rounded-xl border-slate-300 bg-white" disabled>
                    Create from left rail
                  </Button>
                </div>
              </div>
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
