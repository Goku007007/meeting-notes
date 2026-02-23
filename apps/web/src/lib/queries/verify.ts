import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiPost } from "@/lib/api";

export type VerifyActionItem = {
  task: string;
  owner: string | null;
  due_date: string | null;
  evidence_chunk_ids: string[];
};

export type VerifyIssue = {
  type:
    | "contradiction"
    | "missing_owner"
    | "missing_due_date"
    | "vague"
    | "missing_context"
    | "other";
  description: string;
  evidence_chunk_ids: string[];
};

export type VerifyResponse = {
  structured_summary: string;
  decisions: string[];
  action_items: VerifyActionItem[];
  open_questions: string[];
  issues: VerifyIssue[];
  had_retry: boolean;
  invalid_reason_counts: Record<string, number>;
};

export const verifyQueryKey = (meetingId: string) => ["verify", meetingId] as const;

export function useVerify(meetingId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => apiPost<VerifyResponse>(`/meetings/${meetingId}/verify`),
    onSuccess: (data) => {
      queryClient.setQueryData(verifyQueryKey(meetingId), data);
    },
  });
}

export function useVerifyResult(meetingId: string) {
  const queryClient = useQueryClient();

  return useQuery<VerifyResponse | null>({
    queryKey: verifyQueryKey(meetingId),
    queryFn: async () => null,
    enabled: false,
    initialData: () => queryClient.getQueryData<VerifyResponse>(verifyQueryKey(meetingId)) ?? null,
    staleTime: Infinity,
  });
}
