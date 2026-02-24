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
    <div className="flex h-full flex-col p-3">
      <div className="flex h-full flex-col rounded-2xl border border-slate-200/90 bg-white/85 shadow-[0_8px_30px_rgba(15,23,42,0.06)]">
        <div className="space-y-3 border-b border-slate-200/80 p-4">
          <Button
            asChild
            variant="outline"
            className="h-11 w-full justify-start rounded-xl border-slate-300 bg-white text-slate-700"
          >
          <Link href="/workspace" onClick={onNavigate}>
            Home
          </Link>
          </Button>

          <form className="space-y-2" onSubmit={(event) => void onCreateMeeting(event)}>
            <Input
              className="h-11 rounded-xl border-slate-300 bg-white/90"
              placeholder="New meeting title"
              value={newMeetingTitle}
              onChange={(event) => setNewMeetingTitle(event.target.value)}
              maxLength={150}
            />
            {createError ? <p className="text-xs text-red-600">{createError}</p> : null}
            <Button
              type="submit"
              className="h-11 w-full rounded-xl bg-emerald-500 font-semibold text-white hover:bg-emerald-600"
              disabled={createMeeting.isPending}
            >
              {createMeeting.isPending ? "Creating..." : "New meeting"}
            </Button>
          </form>

          <Input
            className="h-11 rounded-xl border-slate-300 bg-white/90"
            placeholder="Search meetings"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
          />
        </div>

        <div className="flex-1 space-y-2 overflow-y-auto p-3">
          {meetingsQuery.isLoading ? (
            <>
              <Skeleton className="h-14 w-full rounded-xl" />
              <Skeleton className="h-14 w-full rounded-xl" />
              <Skeleton className="h-14 w-full rounded-xl" />
            </>
          ) : null}

          {meetingsQuery.isError ? (
            <p className="rounded-xl border border-red-200 bg-red-50 p-2 text-xs text-red-700">
              Failed to load meetings.
            </p>
          ) : null}

          {!meetingsQuery.isLoading && filteredMeetings.length === 0 ? (
            <p className="text-xs text-slate-500">No meetings found.</p>
          ) : null}

          {filteredMeetings.map((meeting) => {
            const isActive = meeting.id === activeMeetingId;
            return (
              <button
                key={meeting.id}
                type="button"
              className={`w-full rounded-xl border p-3 text-left transition ${
                  isActive
                    ? "border-emerald-400 border-l-4 border-l-emerald-500 bg-emerald-50/85 shadow-sm ring-1 ring-emerald-200"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                }`}
                onClick={() => {
                  router.push(`/meetings/${meeting.id}`);
                  onNavigate?.();
                }}
              >
                <p className="line-clamp-1 text-sm font-semibold text-slate-800">{meeting.title}</p>
                <p className="text-xs text-slate-500">{formatDate(meeting.created_at)}</p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
