import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost, apiPostForm } from "@/lib/api";

export type DocumentStatus = "pending" | "processing" | "indexed" | "failed";

export type MeetingDocument = {
  document_id: string;
  meeting_id: string;
  doc_type: string;
  filename: string | null;
  original_filename: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  status: DocumentStatus;
  error: string | null;
  processing_started_at: string | null;
  indexed_at: string | null;
};

export type CreateDocumentInput = {
  doc_type: string;
  filename?: string | null;
  text: string;
};

export type CreateDocumentResponse = {
  document_id: string;
  status: string;
  original_filename?: string | null;
  upload_id?: string | null;
};

export type UploadDocumentInput = {
  doc_type: string;
  file: File;
  filename?: string | null;
  upload_id?: string | null;
};

export function useMeetingDocuments(meetingId: string) {
  return useQuery({
    queryKey: ["meeting-documents", meetingId],
    queryFn: () => apiGet<MeetingDocument[]>(`/meetings/${meetingId}/documents`),
    enabled: Boolean(meetingId),
    refetchInterval: (query) => {
      const docs = (query.state.data ?? []) as MeetingDocument[];
      return docs.some((doc) => doc.status === "pending" || doc.status === "processing")
        ? 2000
        : false;
    },
  });
}

export function useCreateDocument(meetingId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateDocumentInput) =>
      apiPost<CreateDocumentResponse>(`/meetings/${meetingId}/documents`, payload),
    onMutate: async (payload) => {
      const queryKey = ["meeting-documents", meetingId] as const;
      await queryClient.cancelQueries({ queryKey });

      const previousDocs = queryClient.getQueryData<MeetingDocument[]>(queryKey) ?? [];
      const optimisticDoc: MeetingDocument = {
        document_id: `temp-${Date.now()}`,
        meeting_id: meetingId,
        doc_type: payload.doc_type,
        filename: payload.filename ?? null,
        original_filename: payload.filename ?? null,
        mime_type: null,
        size_bytes: null,
        status: "pending",
        error: null,
        processing_started_at: null,
        indexed_at: null,
      };

      queryClient.setQueryData<MeetingDocument[]>(queryKey, [optimisticDoc, ...previousDocs]);
      return { previousDocs };
    },
    onError: (_error, _payload, context) => {
      if (context?.previousDocs) {
        queryClient.setQueryData(["meeting-documents", meetingId], context.previousDocs);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["meeting-documents", meetingId] });
    },
  });
}

export function useUploadDocument(meetingId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: UploadDocumentInput) => {
      const form = new FormData();
      form.append("doc_type", payload.doc_type);
      form.append("file", payload.file);
      if (payload.filename) {
        form.append("filename", payload.filename);
      }
      if (payload.upload_id) {
        form.append("upload_id", payload.upload_id);
      }
      return apiPostForm<CreateDocumentResponse | CreateDocumentResponse[]>(
        `/meetings/${meetingId}/documents/upload`,
        form,
      );
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["meeting-documents", meetingId] });
    },
  });
}

export function useReindexDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (variables: {
      documentId: string;
      meetingId: string;
    }) =>
      apiPost<{ document_id: string; status: string }>(
        `/documents/${variables.documentId}/reindex`,
      ),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["document", variables.documentId] });
      await queryClient.invalidateQueries({ queryKey: ["meeting-documents", variables.meetingId] });
    },
  });
}
