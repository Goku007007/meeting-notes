"use client";

import Link from "next/link";
import { Menu } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { MeetingIndexState } from "@/lib/state/meetingIndexState";

type TopNavProps = {
  isMeetingRoute: boolean;
  meetingTitle: string | null;
  indexState: MeetingIndexState | null;
  onOpenMeetings: () => void;
};

export function TopNav({ isMeetingRoute, meetingTitle, indexState, onOpenMeetings }: TopNavProps) {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-[1700px] items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="icon" className="lg:hidden" onClick={onOpenMeetings}>
            <Menu className="h-4 w-4" />
            <span className="sr-only">Open meetings</span>
          </Button>
          <Button asChild variant="ghost" className="px-2">
            <Link href="/">meeting-notes</Link>
          </Button>
        </div>

        <div className="flex items-center gap-2">
          {isMeetingRoute ? (
            <>
              <span className="max-w-[260px] truncate text-sm font-medium">{meetingTitle ?? "Meeting"}</span>
              {indexState ? <Badge variant="secondary">{indexState}</Badge> : null}
            </>
          ) : (
            <Badge variant="outline">Guest Mode</Badge>
          )}
        </div>
      </div>
    </header>
  );
}
