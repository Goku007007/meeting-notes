"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateDocument } from "@/lib/queries/documents";

const documentUploadSchema = z.object({
  doc_type: z.string().min(1, "Document type is required.").max(50),
  filename: z.string().max(255, "Filename must be 255 characters or less.").optional(),
  text: z.string().min(1, "Notes text is required."),
});

type DocumentUploadValues = z.infer<typeof documentUploadSchema>;

const docTypeOptions = [
  { value: "notes", label: "Notes" },
  { value: "transcript", label: "Transcript" },
  { value: "prd", label: "PRD" },
  { value: "email", label: "Email" },
] as const;

export function DocumentUploadForm({ meetingId }: { meetingId: string }) {
  const [textDraft, setTextDraft] = useState("");
  const createDocument = useCreateDocument(meetingId);
  const {
    register,
    handleSubmit,
    reset,
    clearErrors,
    setError,
    formState: { errors },
  } = useForm<DocumentUploadValues>({
    defaultValues: {
      doc_type: "notes",
      filename: "",
      text: "",
    },
  });

  const canSubmit = textDraft.trim().length > 0 && !createDocument.isPending;

  return (
    <form
      className="space-y-4 rounded-lg border p-4"
      onSubmit={handleSubmit(async (values) => {
        clearErrors();

        const parsed = documentUploadSchema.safeParse({
          doc_type: values.doc_type.trim(),
          filename: values.filename?.trim() ? values.filename.trim() : undefined,
          text: values.text.trim(),
        });

        if (!parsed.success) {
          for (const issue of parsed.error.issues) {
            const field = issue.path[0];
            if (field === "doc_type" || field === "filename" || field === "text") {
              setError(field, { type: "manual", message: issue.message });
            }
          }
          return;
        }

        const payload = {
          doc_type: parsed.data.doc_type,
          filename: parsed.data.filename ?? null,
          text: parsed.data.text,
        };

        try {
          await createDocument.mutateAsync(payload);
          toast.success("Document queued for indexing.");
          reset({
            doc_type: parsed.data.doc_type,
            filename: "",
            text: "",
          });
          setTextDraft("");
        } catch (err) {
          const message =
            err && typeof err === "object" && "message" in err
              ? String(err.message)
              : "Failed to upload document.";
          toast.error(message);
        }
      })}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Document type</span>
          <select
            className="h-10 rounded-md border bg-transparent px-3 text-sm"
            {...register("doc_type")}
          >
            {docTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {errors.doc_type ? <span className="text-xs text-red-600">{errors.doc_type.message}</span> : null}
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Filename (optional)</span>
          <Input placeholder="meeting-notes.txt" {...register("filename")} />
          {errors.filename ? <span className="text-xs text-red-600">{errors.filename.message}</span> : null}
        </label>
      </div>

      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Notes text</span>
        <textarea
          className="min-h-36 w-full rounded-md border bg-transparent px-3 py-2 text-sm"
          placeholder="Paste meeting notes here..."
          {...register("text", {
            onChange: (event) => setTextDraft(event.target.value),
          })}
        />
        {errors.text ? <span className="text-xs text-red-600">{errors.text.message}</span> : null}
      </label>

      <div className="flex justify-end">
        <Button type="submit" disabled={!canSubmit}>
          {createDocument.isPending ? "Uploading..." : "Upload & Index"}
        </Button>
      </div>
    </form>
  );
}
