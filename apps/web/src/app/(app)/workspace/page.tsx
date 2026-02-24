import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function WorkspaceHomePage() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      <Card className="rounded-3xl border-slate-200/90 bg-white/90 shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
        <CardHeader>
          <CardTitle className="text-3xl tracking-tight text-slate-900">Meeting Assistant</CardTitle>
          <CardDescription className="text-base text-slate-500">
            ChatGPT-style workflow for meetings: attach files, ask questions, and verify decisions,
            tasks, and issues.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-base text-slate-600">
          <p>1. Create or select a meeting from the left rail.</p>
          <p>2. Open the meeting and attach files in the chat composer.</p>
          <p>3. Use Verify and artifact tabs on the right rail to review tasks/issues/docs.</p>
          <p className="text-sm text-slate-500">Guest mode: token-based session ownership is enabled.</p>
          <div className="flex flex-wrap gap-2 pt-2">
            <Button className="rounded-xl bg-emerald-500 text-white hover:bg-emerald-600" disabled>
              Create meeting from left rail
            </Button>
            <Button asChild variant="outline" className="rounded-xl border-slate-300 bg-white">
              <Link href="/">Back to landing</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
