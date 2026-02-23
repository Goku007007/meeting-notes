"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type EvidenceDrawerProps = {
  evidenceId: string | null;
  quote: string | null;
  onOpenChange: (open: boolean) => void;
};

export function EvidenceDrawer({ evidenceId, quote, onOpenChange }: EvidenceDrawerProps) {
  return (
    <Dialog open={Boolean(evidenceId)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Evidence</DialogTitle>
          <DialogDescription>Chunk {evidenceId}</DialogDescription>
        </DialogHeader>
        <p className="whitespace-pre-wrap text-sm">{quote ?? "No quote available."}</p>
      </DialogContent>
    </Dialog>
  );
}
