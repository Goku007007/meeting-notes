import type { MeetingDocument } from "@/lib/queries/documents";

export type MeetingIndexState =
  | "EMPTY"
  | "NOT_INDEXED"
  | "PARTIALLY_INDEXED"
  | "INDEXED"
  | "FAILED_ONLY";

export function getMeetingIndexState(documents: MeetingDocument[]): MeetingIndexState {
  // "indexed" documents are treated as user-usable readiness for chat/verify.
  // This mirrors backend behavior where indexed content is considered searchable.
  if (documents.length === 0) {
    return "EMPTY";
  }

  const indexedCount = documents.filter((doc) => doc.status === "indexed").length;
  const pendingOrProcessingCount = documents.filter(
    (doc) => doc.status === "pending" || doc.status === "processing",
  ).length;
  const failedCount = documents.filter((doc) => doc.status === "failed").length;

  if (indexedCount === 0 && pendingOrProcessingCount > 0) {
    return "NOT_INDEXED";
  }

  if (indexedCount > 0 && pendingOrProcessingCount > 0) {
    return "PARTIALLY_INDEXED";
  }

  if (indexedCount > 0 && pendingOrProcessingCount === 0) {
    return "INDEXED";
  }

  if (indexedCount === 0 && failedCount > 0 && pendingOrProcessingCount === 0) {
    return "FAILED_ONLY";
  }

  return "EMPTY";
}
