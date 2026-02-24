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
        className="min-h-24 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 transition-colors placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-200"
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
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="rounded-xl border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:bg-slate-100 disabled:text-slate-500"
          onClick={onAttachClick}
          disabled={attachDisabled}
        >
          <Paperclip className="mr-2 h-4 w-4" />
          {isUploading ? "Uploading..." : "Attach"}
        </Button>
        <Button
          type="button"
          size="sm"
          className="rounded-xl bg-emerald-500 px-5 text-white hover:bg-emerald-600 disabled:bg-emerald-200 disabled:text-emerald-700 disabled:opacity-100"
          onClick={onSend}
          disabled={sendDisabled}
        >
          <Send className="mr-2 h-4 w-4" />
          {isSending ? "Sending..." : isUploading ? "Wait..." : "Send"}
        </Button>
      </div>
    </>
  );
}
