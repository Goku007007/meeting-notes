"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ChatCitation } from "@/lib/queries/chat";
import { useChunkDetail } from "@/lib/queries/chunks";

type CitationDrawerProps = {
  citation: ChatCitation | null;
  onOpenChange: (open: boolean) => void;
};

export function CitationDrawer({ citation, onOpenChange }: CitationDrawerProps) {
  const chunkQuery = useChunkDetail(citation?.chunk_id ?? null);

  return (
    <Dialog open={Boolean(citation)} onOpenChange={onOpenChange}>
      <DialogContent className="border-slate-200 bg-[#f8fbfb]">
        <DialogHeader>
          <DialogTitle>Citation</DialogTitle>
          <DialogDescription>Chunk {citation?.chunk_id}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div>
            <p className="mb-1 text-xs font-medium text-slate-500">Quoted snippet</p>
            <p className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-2">{citation?.quote}</p>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-slate-500">Source chunk text</p>
            {chunkQuery.isLoading ? (
              <p className="text-xs text-slate-500">Loading chunk...</p>
            ) : chunkQuery.isError ? (
              <p className="text-xs text-red-600">Failed to load chunk details.</p>
            ) : (
              <p className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-2">
                {chunkQuery.data?.text ?? "No chunk text available."}
              </p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
