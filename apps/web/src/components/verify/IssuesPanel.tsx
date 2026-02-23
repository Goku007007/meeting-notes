"use client";

import type { VerifyResponse } from "@/lib/queries/verify";

type IssuesPanelProps = {
  verifyResult: VerifyResponse | null;
};

export function IssuesPanel({ verifyResult }: IssuesPanelProps) {
  if (!verifyResult) {
    return (
      <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
        Run Verify to generate issues.
      </p>
    );
  }

  if (verifyResult.issues.length === 0) {
    return <p className="text-sm text-muted-foreground">No issues found in the latest verify run.</p>;
  }

  return (
    <div className="space-y-2">
      {verifyResult.issues.map((issue, index) => (
        <div key={`issue-${index}`} className="rounded-md border p-3">
          <p className="text-sm font-medium">{issue.type}</p>
          <p className="text-xs">{issue.description}</p>
        </div>
      ))}
    </div>
  );
}
