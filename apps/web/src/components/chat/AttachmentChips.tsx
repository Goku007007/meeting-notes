"use client";

import { Loader2, X } from "lucide-react";

import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import { ReindexButton } from "@/components/documents/ReindexButton";
import { Badge } from "@/components/ui/badge";
import type { MeetingDocument } from "@/lib/queries/documents";

export type PendingUploadChip = {
  id: string;
  name: string;
  status: "uploading" | "failed";
  error: string | null;
};

type AttachmentChipsProps = {
  meetingId: string;
  pendingUploads: PendingUploadChip[];
  attachedDocuments: MeetingDocument[];
  onRemovePending: (id: string) => void;
};

export function AttachmentChips({
  meetingId,
  pendingUploads,
  attachedDocuments,
  onRemovePending,
}: AttachmentChipsProps) {
  const hasAny = pendingUploads.length > 0 || attachedDocuments.length > 0;
  if (!hasAny) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50/70 p-2">
      {pendingUploads.map((upload) => (
        <Badge
          key={upload.id}
          variant="secondary"
          className={`gap-1.5 transition-all duration-300 ${
            upload.status === "failed" ? "bg-red-100 text-red-800" : "bg-sky-100 text-sky-900"
          }`}
          title={upload.error ?? undefined}
        >
          {upload.status === "uploading" ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          {upload.name}
          <span className="ml-2 text-xs">{upload.status === "uploading" ? "uploading..." : "failed"}</span>
          {upload.status === "failed" ? (
            <button type="button" className="ml-2 inline-flex" onClick={() => onRemovePending(upload.id)}>
              <X className="h-3 w-3" />
            </button>
          ) : null}
        </Badge>
      ))}

      {attachedDocuments.map((doc) => (
        <Badge
          key={doc.document_id}
          variant="outline"
          className="gap-2 rounded-full border-slate-200 bg-white transition-all duration-300"
        >
          <span className="max-w-[180px] truncate">{doc.filename ?? doc.original_filename ?? doc.document_id}</span>
          <DocumentStatusBadge status={doc.status} />
          {doc.status === "failed" ? (
            <ReindexButton documentId={doc.document_id} meetingId={meetingId} />
          ) : null}
        </Badge>
      ))}
    </div>
  );
}
