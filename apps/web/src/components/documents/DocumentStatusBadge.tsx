import { Badge } from "@/components/ui/badge";
import type { DocumentStatus } from "@/lib/queries/documents";

const statusLabel: Record<DocumentStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  indexed: "Indexed",
  failed: "Failed",
};

const statusClassName: Record<DocumentStatus, string> = {
  pending: "bg-slate-200 text-slate-800",
  processing: "bg-blue-100 text-blue-800",
  indexed: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return <Badge className={statusClassName[status]}>{statusLabel[status]}</Badge>;
}

