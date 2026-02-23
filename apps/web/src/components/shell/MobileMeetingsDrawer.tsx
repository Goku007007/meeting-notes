"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MeetingsRail } from "@/components/shell/MeetingsRail";

type MobileMeetingsDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activeMeetingId?: string | null;
};

export function MobileMeetingsDrawer({
  open,
  onOpenChange,
  activeMeetingId,
}: MobileMeetingsDrawerProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="left-0 top-0 h-screen w-[92vw] max-w-[340px] translate-x-0 translate-y-0 rounded-none border-r p-0 sm:max-w-[340px]">
        <DialogHeader className="sr-only">
          <DialogTitle>Meetings</DialogTitle>
          <DialogDescription>Open or create meetings.</DialogDescription>
        </DialogHeader>
        <MeetingsRail activeMeetingId={activeMeetingId} onNavigate={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
