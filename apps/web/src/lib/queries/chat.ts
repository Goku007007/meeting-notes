import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/lib/api";

export type ChatCitation = {
  chunk_id: string;
  quote: string;
};

export type ChatResponse = {
  answer: string;
  citations: ChatCitation[];
  run_id: string | null;
};

export type ChatHistoryTurn = {
  run_id: string;
  question: string;
  answer: string | null;
  citations: ChatCitation[];
  created_at: string;
};

export const chatHistoryQueryKey = (meetingId: string) => ["chat-history", meetingId] as const;

export function useChatHistory(meetingId: string) {
  return useQuery({
    queryKey: chatHistoryQueryKey(meetingId),
    queryFn: () => apiGet<ChatHistoryTurn[]>(`/meetings/${meetingId}/chat/history`),
    enabled: Boolean(meetingId),
  });
}

export function useChat(meetingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (question: string) =>
      apiPost<ChatResponse>(`/meetings/${meetingId}/chat`, { question }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: chatHistoryQueryKey(meetingId) });
    },
  });
}

export function useChatFeedback(meetingId: string) {
  return useMutation({
    mutationFn: async (payload: { run_id: string; verdict: "up" | "down"; reason?: string }) =>
      apiPost<{ ok: boolean }>(`/meetings/${meetingId}/chat/feedback`, payload),
  });
}
