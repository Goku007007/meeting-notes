import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type MeetingWorkspacePageProps = {
  params: Promise<{
    meetingId: string;
  }>;
};

export default async function MeetingWorkspacePage({ params }: MeetingWorkspacePageProps) {
  const { meetingId } = await params;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-6 p-6 md:p-10">
      <section className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Meeting Workspace</h1>
        <Button asChild variant="outline">
          <Link href="/">Back to meetings</Link>
        </Button>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Meeting ID</CardTitle>
          <CardDescription>This is a placeholder workspace route for now.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="break-all text-sm text-muted-foreground">{meetingId}</p>
        </CardContent>
      </Card>
    </main>
  );
}

