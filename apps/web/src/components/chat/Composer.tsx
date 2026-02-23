"use client";

import { Paperclip, Send } from "lucide-react";

import { Button } from "@/components/ui/button";

type ComposerProps = {
  question: string;
  disabled: boolean;
  isSending: boolean;
  onQuestionChange: (value: string) => void;
  onSend: () => void;
  onAttachClick: () => void;
};

export function Composer({
  question,
  disabled,
  isSending,
  onQuestionChange,
  onSend,
  onAttachClick,
}: ComposerProps) {
  return (
    <>
      <textarea
        className="min-h-24 w-full rounded-md border bg-transparent px-3 py-2 text-sm"
        placeholder="Ask a question about this meeting..."
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        disabled={disabled}
      />
      <div className="flex items-center justify-between">
        <Button type="button" variant="outline" size="sm" onClick={onAttachClick}>
          <Paperclip className="mr-2 h-4 w-4" />
          Attach
        </Button>
        <Button type="button" size="sm" onClick={onSend} disabled={disabled || !question.trim() || isSending}>
          <Send className="mr-2 h-4 w-4" />
          {isSending ? "Sending..." : "Send"}
        </Button>
      </div>
    </>
  );
}
