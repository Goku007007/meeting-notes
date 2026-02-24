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
    <Card className="rounded-2xl border border-slate-200/90 bg-white/90 py-4 shadow-sm">
      <CardHeader>
        <CardTitle className="text-3xl tracking-tight text-slate-900">Verify</CardTitle>
        <CardDescription className="text-base text-slate-500">
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
            className="rounded-xl bg-emerald-500 text-white hover:bg-emerald-600 disabled:bg-emerald-200 disabled:text-emerald-700 disabled:opacity-100"
          >
            {verifyMutation.isPending ? "Running..." : "Run Verify"}
          </Button>
          {lastRunAt ? (
            <span className="text-xs text-slate-500">Last run: {lastRunAt}</span>
          ) : null}
        </div>

        {!canRunVerify(indexState) ? (
          <p className="rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
            Verify is enabled after at least one document is indexed.
          </p>
        ) : null}

        {verifyResult ? (
          <div className="space-y-3 text-sm">
            <details open>
              <summary className="cursor-pointer font-medium">Summary & Decisions</summary>
              <p className="mt-2 whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50/70 p-3">
                {verifyResult.structured_summary}
              </p>
              {verifyResult.decisions.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {verifyResult.decisions.map((decision, index) => (
                    <li key={`decision-${index}`}>{decision}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-slate-500">No decisions extracted.</p>
              )}
            </details>
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            Run verify to generate structured artifacts from indexed notes.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
