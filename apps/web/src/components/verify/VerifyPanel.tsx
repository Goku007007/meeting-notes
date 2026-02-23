"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useVerify, useVerifyResult } from "@/lib/queries/verify";
import type { MeetingIndexState } from "@/lib/state/meetingIndexState";

type VerifyPanelProps = {
  meetingId: string;
  indexState: MeetingIndexState;
};

function canRunVerify(indexState: MeetingIndexState): boolean {
  return indexState === "INDEXED" || indexState === "PARTIALLY_INDEXED";
}

export function VerifyPanel({ meetingId, indexState }: VerifyPanelProps) {
  const verifyMutation = useVerify(meetingId);
  const verifyResult = useVerifyResult(meetingId).data;
  const [lastRunAt, setLastRunAt] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Verify</CardTitle>
        <CardDescription>
          Extract decisions, action items, and issues with evidence.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <Button
            type="button"
            onClick={async () => {
              try {
                await verifyMutation.mutateAsync();
                setLastRunAt(new Date().toLocaleString());
              } catch (err) {
                const message =
                  err && typeof err === "object" && "message" in err
                    ? String(err.message)
                    : "Verify failed.";
                toast.error(message);
              }
            }}
            disabled={!canRunVerify(indexState) || verifyMutation.isPending}
          >
            {verifyMutation.isPending ? "Running..." : "Run Verify"}
          </Button>
          {lastRunAt ? (
            <span className="text-xs text-muted-foreground">Last run: {lastRunAt}</span>
          ) : null}
        </div>

        {!canRunVerify(indexState) ? (
          <p className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
            Verify is enabled after at least one document is indexed.
          </p>
        ) : null}

        {verifyResult ? (
          <div className="space-y-3 text-sm">
            <details open>
              <summary className="cursor-pointer font-medium">Summary & Decisions</summary>
              <p className="mt-2 whitespace-pre-wrap rounded-md border p-3">
                {verifyResult.structured_summary}
              </p>
              {verifyResult.decisions.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {verifyResult.decisions.map((decision, index) => (
                    <li key={`decision-${index}`}>{decision}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-muted-foreground">No decisions extracted.</p>
              )}
            </details>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Run verify to generate structured artifacts from indexed notes.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
