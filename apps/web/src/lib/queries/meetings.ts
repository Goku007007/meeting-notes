import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/lib/api";

export type Meeting = {
  id: string;
  title: string;
  created_at: string;
};

export const meetingsQueryKey = ["meetings"] as const;

export function useMeetings() {
  return useQuery({
    queryKey: meetingsQueryKey,
    queryFn: () => apiGet<Meeting[]>("/meetings"),
  });
}

export function useMeeting(meetingId: string) {
  return useQuery({
    queryKey: ["meeting", meetingId],
    queryFn: () => apiGet<Meeting>(`/meetings/${meetingId}`),
    enabled: Boolean(meetingId),
  });
}

export function useCreateMeeting() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (title: string) => {
      const params = new URLSearchParams({ title });
      return apiPost<Meeting>(`/meetings?${params.toString()}`);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: meetingsQueryKey });
    },
  });
}

