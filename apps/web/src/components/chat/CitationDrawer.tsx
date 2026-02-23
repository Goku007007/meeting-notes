"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ChatCitation } from "@/lib/queries/chat";

type CitationDrawerProps = {
  citation: ChatCitation | null;
  onOpenChange: (open: boolean) => void;
};

export function CitationDrawer({ citation, onOpenChange }: CitationDrawerProps) {
  return (
    <Dialog open={Boolean(citation)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Citation</DialogTitle>
          <DialogDescription>Chunk {citation?.chunk_id}</DialogDescription>
        </DialogHeader>
        <p className="whitespace-pre-wrap text-sm">{citation?.quote}</p>
      </DialogContent>
    </Dialog>
  );
}
