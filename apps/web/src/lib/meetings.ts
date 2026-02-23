import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "./api";

export type Meeting = {
  id: string;
  title: string;
};

const MEETINGS_QUERY_KEY = ["meetings"] as const;

export function useMeetings() {
  return useQuery({
    queryKey: MEETINGS_QUERY_KEY,
    queryFn: () => apiGet<Meeting[]>("/meetings"),
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
      // Keep the meetings list in sync after creating a new meeting.
      await queryClient.invalidateQueries({ queryKey: MEETINGS_QUERY_KEY });
    },
  });
}

