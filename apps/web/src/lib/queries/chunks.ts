import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";

export type ChunkDetail = {
  chunk_id: string;
  meeting_id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  document_filename: string | null;
  document_original_filename: string | null;
  document_doc_type: string | null;
};

export function useChunkDetail(chunkId: string | null) {
  return useQuery({
    queryKey: ["chunk-detail", chunkId],
    queryFn: () => apiGet<ChunkDetail>(`/chunks/${chunkId}`),
    enabled: Boolean(chunkId),
  });
}
