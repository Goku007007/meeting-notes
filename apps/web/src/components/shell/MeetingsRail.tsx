"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateMeeting, useMeetings } from "@/lib/queries/meetings";

type MeetingsRailProps = {
  activeMeetingId?: string | null;
  onNavigate?: () => void;
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString();
}

export function MeetingsRail({ activeMeetingId, onNavigate }: MeetingsRailProps) {
  const router = useRouter();
  const [newMeetingTitle, setNewMeetingTitle] = useState("");
  const [searchText, setSearchText] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const meetingsQuery = useMeetings();
  const createMeeting = useCreateMeeting();

  const filteredMeetings = useMemo(() => {
    const meetings = meetingsQuery.data ?? [];
    const query = searchText.trim().toLowerCase();
    if (!query) return meetings;
    return meetings.filter((meeting) => meeting.title.toLowerCase().includes(query));
  }, [meetingsQuery.data, searchText]);

  async function onCreateMeeting(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const title = newMeetingTitle.trim();
    if (!title) {
      setCreateError("Meeting title is required.");
      return;
    }

    setCreateError(null);
    try {
      const created = await createMeeting.mutateAsync(title);
      setNewMeetingTitle("");
      router.push(`/meetings/${created.id}`);
      onNavigate?.();
    } catch (err) {
      const message =
        err && typeof err === "object" && "message" in err
          ? String(err.message)
          : "Failed to create meeting.";
      setCreateError(message);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-3 border-b p-4">
        <Button asChild variant="outline" className="w-full justify-start">
          <Link href="/workspace" onClick={onNavigate}>
            Home
          </Link>
        </Button>

        <form className="space-y-2" onSubmit={(event) => void onCreateMeeting(event)}>
          <Input
            placeholder="New meeting title"
            value={newMeetingTitle}
            onChange={(event) => setNewMeetingTitle(event.target.value)}
            maxLength={150}
          />
          {createError ? <p className="text-xs text-red-600">{createError}</p> : null}
          <Button type="submit" className="w-full" disabled={createMeeting.isPending}>
            {createMeeting.isPending ? "Creating..." : "New meeting"}
          </Button>
        </form>

        <Input
          placeholder="Search meetings"
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
        />
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {meetingsQuery.isLoading ? (
          <>
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </>
        ) : null}

        {meetingsQuery.isError ? (
          <p className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
            Failed to load meetings.
          </p>
        ) : null}

        {!meetingsQuery.isLoading && filteredMeetings.length === 0 ? (
          <p className="text-xs text-muted-foreground">No meetings found.</p>
        ) : null}

        {filteredMeetings.map((meeting) => {
          const isActive = meeting.id === activeMeetingId;
          return (
            <button
              key={meeting.id}
              type="button"
              className={`w-full rounded-md border p-3 text-left transition ${
                isActive ? "border-primary bg-primary/10" : "hover:bg-muted/60"
              }`}
              onClick={() => {
                router.push(`/meetings/${meeting.id}`);
                onNavigate?.();
              }}
            >
              <p className="line-clamp-1 text-sm font-medium">{meeting.title}</p>
              <p className="text-xs text-muted-foreground">{formatDate(meeting.created_at)}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
