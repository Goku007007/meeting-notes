"use client";

import type { VerifyResponse } from "@/lib/queries/verify";

type TasksPanelProps = {
  verifyResult: VerifyResponse | null;
};

export function TasksPanel({ verifyResult }: TasksPanelProps) {
  if (!verifyResult) {
    return (
      <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
        Run Verify to generate tasks.
      </p>
    );
  }

  if (verifyResult.action_items.length === 0) {
    return <p className="text-sm text-muted-foreground">No action items found in the latest verify run.</p>;
  }

  return (
    <div className="space-y-2">
      {verifyResult.action_items.map((item, index) => (
        <div key={`task-${index}`} className="rounded-md border p-3">
          <p className="text-sm font-medium">{item.task}</p>
          <p className="text-xs text-muted-foreground">
            Owner: {item.owner ?? "Missing"} · Due: {item.due_date ?? "Missing"}
          </p>
        </div>
      ))}
    </div>
  );
}
