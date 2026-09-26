"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import {
  FileText,
  FileUser,
  Loader2,
  Trash2,
  TriangleAlert,
  Upload,
} from "lucide-react";

import { ProfileSection } from "@/components/profile/profile-section";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  deleteResume,
  RESUME_TOO_LARGE_MESSAGE,
  RESUME_WRONG_TYPE_MESSAGE,
  uploadResume,
  type ResumeInfo,
  type ResumeUpload,
} from "@/lib/api/preferences";
import { cn } from "@/lib/utils";

const MAX_RESUME_BYTES = 10 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".pdf", ".docx"];
const ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const FILE_TYPE_LABELS: Record<ResumeInfo["file_type"], string> = {
  pdf: "PDF document",
  docx: "Word document",
};

type Busy = "uploading" | "deleting" | null;

type ResumeCardProps = {
  resume: ResumeInfo | null;
  /** Called after a successful upload with the stored resume and any suggestions. */
  onUploaded: (upload: ResumeUpload) => void;
  onDeleted: () => void;
};

function formatUploadedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

/** Checks the server repeats, done first so obviously wrong files are not uploaded at all. */
function checkFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return RESUME_WRONG_TYPE_MESSAGE;
  }
  if (file.size > MAX_RESUME_BYTES) {
    return RESUME_TOO_LARGE_MESSAGE;
  }
  return null;
}

/** Current resume with Upload / Replace and Delete (after an inline confirmation). */
export function ResumeCard({ resume, onUploaded, onDeleted }: ResumeCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cancelDeleteRef = useRef<HTMLButtonElement>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    if (confirmingDelete) {
      cancelDeleteRef.current?.focus();
    }
  }, [confirmingDelete]);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Reset so choosing the same file again still fires `change`.
    event.target.value = "";
    if (!file || busy) {
      return;
    }
    setError(null);
    setWarning(null);
    setConfirmingDelete(false);

    const problem = checkFile(file);
    if (problem) {
      setError(problem);
      return;
    }

    setBusy("uploading");
    const result = await uploadResume(file);
    setBusy(null);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setWarning(result.suggestions === null ? result.warning : null);
    onUploaded(result);
  }

  async function handleDelete() {
    if (busy) {
      return;
    }
    setError(null);
    setWarning(null);
    setBusy("deleting");
    const result = await deleteResume();
    setBusy(null);
    setConfirmingDelete(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    onDeleted();
  }

  const isBusy = busy !== null;

  return (
    <ProfileSection
      id="resume"
      title="Resume"
      icon={FileUser}
      description="Upload a PDF or Word (.docx) file up to 10 MB. It is read to suggest job titles and skills, and to score new jobs."
    >
      <div className="flex flex-col gap-4" aria-busy={isBusy}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-surface-alt text-accent">
              <FileText className="size-5" aria-hidden="true" />
            </span>
            {resume ? (
              <div className="min-w-0">
                <p className="font-medium">
                  {FILE_TYPE_LABELS[resume.file_type]}
                </p>
                <p className="text-sm text-muted-foreground">
                  Uploaded {formatUploadedAt(resume.uploaded_at)}
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No resume uploaded yet.
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <input
              ref={fileInputRef}
              id="resume-file"
              type="file"
              accept={ACCEPT}
              className="sr-only"
              tabIndex={-1}
              aria-label="Resume file"
              onChange={handleFileChange}
              disabled={isBusy}
            />
            <Button
              type="button"
              variant={resume ? "outline" : "default"}
              onClick={() => fileInputRef.current?.click()}
              disabled={isBusy}
              aria-busy={busy === "uploading"}
            >
              {busy === "uploading" ? (
                <Loader2 className="animate-spin" aria-hidden="true" />
              ) : (
                <Upload aria-hidden="true" />
              )}
              {resume ? "Replace resume" : "Upload resume"}
            </Button>
            {resume && !confirmingDelete && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => setConfirmingDelete(true)}
                disabled={isBusy}
              >
                <Trash2 aria-hidden="true" />
                Delete
              </Button>
            )}
          </div>
        </div>

        {confirmingDelete && (
          <div
            role="group"
            aria-labelledby="resume-delete-question"
            className="flex flex-col gap-3 rounded-lg border border-border bg-surface-alt p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <p id="resume-delete-question" className="text-sm">
              Delete your resume? Your titles and skills stay as they are.
            </p>
            <div className="flex gap-2">
              <Button
                ref={cancelDeleteRef}
                type="button"
                variant="outline"
                onClick={() => setConfirmingDelete(false)}
                disabled={isBusy}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={handleDelete}
                disabled={isBusy}
                aria-busy={busy === "deleting"}
              >
                {busy === "deleting" && (
                  <Loader2 className="animate-spin" aria-hidden="true" />
                )}
                Delete resume
              </Button>
            </div>
          </div>
        )}

        <p
          aria-live="polite"
          className={cn("text-sm text-muted-foreground", !isBusy && "sr-only")}
        >
          {busy === "uploading"
            ? "Uploading and reading your resume. This can take a moment…"
            : busy === "deleting"
              ? "Deleting your resume…"
              : ""}
        </p>

        {error && (
          <Alert variant="destructive">
            <TriangleAlert aria-hidden="true" />
            <AlertDescription className="text-destructive">
              {error}
            </AlertDescription>
          </Alert>
        )}
        {warning && (
          <Alert variant="warning" role="status">
            <TriangleAlert aria-hidden="true" />
            <AlertDescription className="text-foreground">
              {warning}
            </AlertDescription>
          </Alert>
        )}
      </div>
    </ProfileSection>
  );
}
