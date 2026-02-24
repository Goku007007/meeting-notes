import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-4xl space-y-6 p-4 md:p-6">
      <Card>
        <CardHeader>
          <CardTitle>Meeting Assistant</CardTitle>
          <CardDescription>
            ChatGPT-style workflow for meetings: attach files, ask questions, and verify decisions,
            tasks, and issues.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>1. Create or select a meeting from the left rail.</p>
          <p>2. Open the meeting and attach files in the chat composer.</p>
          <p>3. Use Verify and artifact tabs on the right rail to review tasks/issues/docs.</p>
          <p className="text-xs">Guest mode: token-based session ownership is enabled.</p>
        </CardContent>
      </Card>
    </main>
  );
}
