"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { MeetingWorkspace } from "@/components/layout/MeetingWorkspace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMeeting } from "@/lib/queries/meetings";

export default function MeetingWorkspacePage() {
  const params = useParams<{ meetingId: string }>();
  const meetingId = params?.meetingId ?? "";
  const meetingQuery = useMeeting(meetingId);

  if (meetingQuery.isLoading) {
    return (
      <main className="mx-auto max-w-5xl space-y-4 p-4 md:p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </main>
    );
  }

  if (meetingQuery.isError || !meetingQuery.data) {
    const message =
      meetingQuery.error && typeof meetingQuery.error === "object" && "message" in meetingQuery.error
        ? String(meetingQuery.error.message)
        : "Failed to load meeting.";

    return (
      <main className="mx-auto max-w-3xl p-4 md:p-6">
        <Card className="border-red-200">
          <CardHeader>
            <CardTitle className="text-red-700">Meeting unavailable</CardTitle>
            <CardDescription>{message}</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2">
            <Button type="button" onClick={() => void meetingQuery.refetch()}>
              Retry
            </Button>
            <Button asChild variant="outline">
              <Link href="/workspace">Home</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  return <MeetingWorkspace meetingId={meetingId} />;
}
