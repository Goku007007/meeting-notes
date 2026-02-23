"use client";

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useReindexDocument } from "@/lib/queries/documents";

type ReindexButtonProps = {
  documentId: string;
  meetingId: string;
  disabled?: boolean;
  onError?: (message: string) => void;
};

export function ReindexButton({ documentId, meetingId, disabled, onError }: ReindexButtonProps) {
  const reindexMutation = useReindexDocument();
  const isSubmitting = reindexMutation.isPending;

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      disabled={disabled || isSubmitting}
      onClick={async () => {
        try {
          await reindexMutation.mutateAsync({ documentId, meetingId });
        } catch (err) {
          const message =
            err && typeof err === "object" && "message" in err
              ? String(err.message)
              : "Failed to reindex document.";
          onError?.(message);
        }
      }}
    >
      {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
      Reindex
    </Button>
  );
}

