import { useMutation } from "@tanstack/react-query";

import { apiPost } from "@/lib/api";

export type ChatCitation = {
  chunk_id: string;
  quote: string;
};

export type ChatResponse = {
  answer: string;
  citations: ChatCitation[];
};

export function useChat(meetingId: string) {
  return useMutation({
    mutationFn: async (question: string) =>
      apiPost<ChatResponse>(`/meetings/${meetingId}/chat`, { question }),
  });
}
