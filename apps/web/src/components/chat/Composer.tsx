"use client";

import { Paperclip, Send } from "lucide-react";

import { Button } from "@/components/ui/button";

type ComposerProps = {
  question: string;
  disabled: boolean;
  isSending: boolean;
  isUploading: boolean;
  onQuestionChange: (value: string) => void;
  onSend: () => void;
  onAttachClick: () => void;
};

export function Composer({
  question,
  disabled,
  isSending,
  isUploading,
  onQuestionChange,
  onSend,
  onAttachClick,
}: ComposerProps) {
  const sendDisabled = disabled || !question.trim() || isSending || isUploading;
  const attachDisabled = isUploading || isSending;

  return (
    <>
      <textarea
        className="min-h-24 w-full rounded-md border bg-transparent px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        placeholder="Ask a question about this meeting..."
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        disabled={disabled}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (!sendDisabled) onSend();
          }
        }}
      />
      <div className="flex items-center justify-between">
        <Button type="button" variant="outline" size="sm" onClick={onAttachClick} disabled={attachDisabled}>
          <Paperclip className="mr-2 h-4 w-4" />
          {isUploading ? "Uploading..." : "Attach"}
        </Button>
        <Button type="button" size="sm" onClick={onSend} disabled={sendDisabled}>
          <Send className="mr-2 h-4 w-4" />
          {isSending ? "Sending..." : isUploading ? "Wait..." : "Send"}
        </Button>
      </div>
    </>
  );
}
