"use client";

import type { VerifyResponse } from "@/lib/queries/verify";

type TasksPanelProps = {
  verifyResult: VerifyResponse | null;
};

export function TasksPanel({ verifyResult }: TasksPanelProps) {
  if (!verifyResult) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-3 text-sm text-slate-500">
        Run Verify to generate tasks.
      </p>
    );
  }

  if (verifyResult.action_items.length === 0) {
    return <p className="text-sm text-slate-500">No action items found in the latest verify run.</p>;
  }

  return (
    <div className="space-y-2">
      {verifyResult.action_items.map((item, index) => (
        <div key={`task-${index}`} className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
          <p className="text-sm font-medium text-slate-800">{item.task}</p>
          <p className="text-xs text-slate-500">
            Owner: {item.owner ?? "Missing"} · Due: {item.due_date ?? "Missing"}
          </p>
        </div>
      ))}
    </div>
  );
}
