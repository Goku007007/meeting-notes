"use client";

import { ReindexButton } from "@/components/documents/ReindexButton";
import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { MeetingDocument } from "@/lib/queries/documents";

type DocumentsPanelProps = {
  meetingId: string;
  documents: MeetingDocument[];
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

export function DocumentsPanel({ meetingId, documents }: DocumentsPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Documents</CardTitle>
        <CardDescription>Background indexing status and retry actions.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
        ) : null}
        {documents.map((doc) => (
          <div key={doc.document_id} className="space-y-2 rounded-md border p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="max-w-[220px] truncate text-sm font-medium">
                {doc.filename ?? doc.original_filename ?? doc.document_id}
              </p>
              <DocumentStatusBadge status={doc.status} />
            </div>
            <p className="text-xs text-muted-foreground">
              {doc.doc_type} · {doc.mime_type ?? "unknown mime"}
            </p>
            <p className="text-xs text-muted-foreground">
              Indexed: {formatDate(doc.indexed_at)}
            </p>
            {doc.error ? (
              <p className="text-xs text-red-700" title={doc.error}>
                {doc.error}
              </p>
            ) : null}
            {doc.status === "failed" ? (
              <ReindexButton documentId={doc.document_id} meetingId={meetingId} />
            ) : null}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
