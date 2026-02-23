"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateMeeting, useMeetings } from "@/lib/meetings";

export default function Home() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const {
    data: meetings,
    isLoading,
    isError,
    error,
    refetch,
  } = useMeetings();
  const createMeeting = useCreateMeeting();

  async function onCreateMeeting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setCreateError("Meeting title is required.");
      return;
    }

    setCreateError(null);
    try {
      await createMeeting.mutateAsync(trimmedTitle);
      setTitle("");
      setIsDialogOpen(false);
    } catch (err) {
      const message = err && typeof err === "object" && "message" in err
        ? String(err.message)
        : "Failed to create meeting.";
      setCreateError(message);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-8 p-6 md:p-10">
      <section className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Meetings</h1>
          <p className="text-sm text-muted-foreground">
            Create a meeting and open a workspace for docs, verify, and chat.
          </p>
        </div>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button>New Meeting</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create meeting</DialogTitle>
              <DialogDescription>Give your meeting a clear title.</DialogDescription>
            </DialogHeader>
            <form className="space-y-4" onSubmit={onCreateMeeting}>
              <Input
                placeholder="e.g. Sprint Planning"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={150}
              />
              {createError ? (
                <p className="text-sm text-red-600">{createError}</p>
              ) : null}
              <DialogFooter>
                <Button type="submit" disabled={createMeeting.isPending}>
                  {createMeeting.isPending ? "Creating..." : "Create"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </section>

      {isLoading ? (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Card key={index}>
              <CardHeader>
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-full" />
              </CardContent>
              <CardFooter>
                <Skeleton className="h-10 w-24" />
              </CardFooter>
            </Card>
          ))}
        </section>
      ) : null}

      {isError ? (
        <Card className="border-red-200">
          <CardHeader>
            <CardTitle className="text-red-700">Failed to load meetings</CardTitle>
            <CardDescription>
              {error && typeof error === "object" && "message" in error
                ? String(error.message)
                : "An unknown error occurred."}
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </CardFooter>
        </Card>
      ) : null}

      {!isLoading && !isError ? (
        meetings && meetings.length > 0 ? (
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {meetings.map((meeting) => (
              <Card key={meeting.id}>
                <CardHeader>
                  <CardTitle className="line-clamp-2 text-lg">{meeting.title}</CardTitle>
                  <CardDescription>{meeting.id}</CardDescription>
                </CardHeader>
                <CardFooter>
                  <Button asChild>
                    <Link href={`/meetings/${meeting.id}`}>Open workspace</Link>
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </section>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>No meetings yet</CardTitle>
              <CardDescription>Create your first meeting to get started.</CardDescription>
            </CardHeader>
          </Card>
        )
      ) : null}
    </main>
  );
}
