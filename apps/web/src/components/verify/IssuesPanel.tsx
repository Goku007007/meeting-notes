"use client";

import type { VerifyResponse } from "@/lib/queries/verify";

type IssuesPanelProps = {
  verifyResult: VerifyResponse | null;
};

export function IssuesPanel({ verifyResult }: IssuesPanelProps) {
  if (!verifyResult) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-3 text-sm text-slate-500">
        Run Verify to generate issues.
      </p>
    );
  }

  if (verifyResult.issues.length === 0) {
    return <p className="text-sm text-slate-500">No issues found in the latest verify run.</p>;
  }

  return (
    <div className="space-y-2">
      {verifyResult.issues.map((issue, index) => (
        <div key={`issue-${index}`} className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
          <p className="text-sm font-medium text-slate-800">{issue.type}</p>
          <p className="text-xs text-slate-600">{issue.description}</p>
        </div>
      ))}
    </div>
  );
}
