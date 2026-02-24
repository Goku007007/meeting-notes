"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useChunkDetail } from "@/lib/queries/chunks";

type EvidenceDrawerProps = {
  evidenceId: string | null;
  quote: string | null;
  onOpenChange: (open: boolean) => void;
};

export function EvidenceDrawer({ evidenceId, quote, onOpenChange }: EvidenceDrawerProps) {
  const chunkQuery = useChunkDetail(evidenceId);

  return (
    <Dialog open={Boolean(evidenceId)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Evidence</DialogTitle>
          <DialogDescription>Chunk {evidenceId}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <p className="whitespace-pre-wrap rounded-md border bg-muted/30 p-2">
            {quote ?? "No quote available."}
          </p>
          {chunkQuery.isLoading ? <p className="text-xs text-muted-foreground">Loading chunk...</p> : null}
          {chunkQuery.isError ? <p className="text-xs text-red-600">Failed to load chunk details.</p> : null}
          {chunkQuery.data ? (
            <p className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-md border p-2">
              {chunkQuery.data.text}
            </p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
