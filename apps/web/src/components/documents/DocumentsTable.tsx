import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { MeetingDocument } from "@/lib/queries/documents";

import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { ReindexButton } from "./ReindexButton";

type DocumentsTableProps = {
  documents: MeetingDocument[];
  meetingId: string;
  reindexError: string | null;
  setReindexError: (message: string | null) => void;
};

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return date.toLocaleString();
}

export function DocumentsTable({
  documents,
  meetingId,
  reindexError,
  setReindexError,
}: DocumentsTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Documents</CardTitle>
        <CardDescription>Latest documents for this meeting.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {reindexError ? <p className="text-sm text-red-700">{reindexError}</p> : null}
        {documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Type</th>
                  <th className="py-2 pr-3 font-medium">Filename</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Processing started</th>
                  <th className="py-2 pr-3 font-medium">Indexed at</th>
                  <th className="py-2 pr-3 font-medium">Error</th>
                  <th className="py-2 pr-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.document_id} className="border-b align-top">
                    <td className="py-3 pr-3">{doc.doc_type}</td>
                    <td className="py-3 pr-3">{doc.filename ?? "—"}</td>
                    <td className="py-3 pr-3">
                      <DocumentStatusBadge status={doc.status} />
                    </td>
                    <td className="py-3 pr-3">{formatDate(doc.processing_started_at)}</td>
                    <td className="py-3 pr-3">{formatDate(doc.indexed_at)}</td>
                    <td className="max-w-[240px] py-3 pr-3">
                      {doc.error ? (
                        <span className="block truncate text-red-700" title={doc.error}>
                          {doc.error}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3 pr-3">
                      {doc.status === "failed" ? (
                        <ReindexButton
                          documentId={doc.document_id}
                          meetingId={meetingId}
                          onError={(message) => setReindexError(message)}
                        />
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

