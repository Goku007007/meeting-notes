"use client";

import { useMemo, useState } from "react";

import { DocumentsPanel } from "@/components/documents/DocumentsPanel";
import { IssuesPanel } from "@/components/verify/IssuesPanel";
import { TasksPanel } from "@/components/verify/TasksPanel";
import { VerifyPanel } from "@/components/verify/VerifyPanel";
import { Button } from "@/components/ui/button";
import type { MeetingDocument } from "@/lib/queries/documents";
import { useVerifyResult } from "@/lib/queries/verify";
import type { MeetingIndexState } from "@/lib/state/meetingIndexState";

type ArtifactsRailProps = {
  meetingId: string;
  documents: MeetingDocument[];
  indexState: MeetingIndexState;
};

type ArtifactsTab = "verify" | "tasks" | "issues" | "docs";

export function ArtifactsRail({ meetingId, documents, indexState }: ArtifactsRailProps) {
  const [activeTab, setActiveTab] = useState<ArtifactsTab>("verify");
  const verifyResult = useVerifyResult(meetingId).data;

  const content = useMemo(() => {
    if (activeTab === "verify") {
      return <VerifyPanel meetingId={meetingId} indexState={indexState} />;
    }
    if (activeTab === "tasks") {
      return <TasksPanel verifyResult={verifyResult ?? null} />;
    }
    if (activeTab === "issues") {
      return <IssuesPanel verifyResult={verifyResult ?? null} />;
    }
    return <DocumentsPanel meetingId={meetingId} documents={documents} />;
  }, [activeTab, documents, indexState, meetingId, verifyResult]);

  return (
    <div className="flex h-full flex-col p-3">
      <div className="flex h-full flex-col rounded-2xl border border-slate-200/90 bg-white/85 shadow-[0_8px_30px_rgba(15,23,42,0.06)]">
        <div className="flex flex-wrap gap-2 border-b border-slate-200/80 p-3">
        {(["verify", "tasks", "issues", "docs"] as const).map((tab) => (
          <Button
            key={tab}
            type="button"
            size="sm"
            className={`rounded-xl ${
              activeTab === tab
                ? "bg-emerald-500 text-white shadow-sm hover:bg-emerald-600"
                : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100"
            }`}
            variant={activeTab === tab ? "default" : "outline"}
            onClick={() => setActiveTab(tab)}
          >
            {tab === "docs" ? "Docs" : tab.charAt(0).toUpperCase() + tab.slice(1)}
          </Button>
        ))}
        </div>
        <div key={activeTab} className="flex-1 overflow-y-auto p-3 animate-in fade-in duration-200">
          {content}
        </div>
      </div>
    </div>
  );
}
