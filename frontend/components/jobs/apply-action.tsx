"use client";

import { useRef, useState } from "react";
import { CircleCheck, ExternalLink, LoaderCircle, Send } from "lucide-react";

import { useAnnounce } from "@/components/ui/announcer";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { applyToJob, type JobDetail } from "@/lib/api/jobs";
import { formatDate } from "@/lib/jobs/format";

type ApplyActionProps = {
  job: Pick<JobDetail, "id" | "title" | "url" | "inbox_type" | "applied_when">;
  /** Receives the job after it was marked as applied. */
  onApplied: (job: JobDetail) => void;
};

/**
 * Apply opens the posting in a new tab, then asks "Did you apply?". Only "Yes" marks the job as
 * applied; "No" or dismissing changes nothing. An applied job shows its date and the posting.
 */
export function ApplyAction({ job, onApplied }: ApplyActionProps) {
  const announce = useAnnounce();
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const postingLinkRef = useRef<HTMLAnchorElement>(null);
  const justApplied = useRef(false);

  const applied = job.applied_when !== null || job.inbox_type === "applied";

  function openPosting() {
    // Opened inside the click so popup blockers allow it.
    window.open(job.url, "_blank", "noopener,noreferrer");
    setError(null);
    setConfirming(true);
  }

  async function confirmApplied() {
    if (saving) {
      return;
    }
    setSaving(true);
    setError(null);
    const result = await applyToJob(job.id);
    setSaving(false);
    if (!result.ok) {
      setError(result.message);
      announce(
        `Could not mark ${job.title} as applied. ${result.message}`,
        "error",
      );
      return;
    }
    justApplied.current = true;
    setConfirming(false);
    onApplied(result.job);
    announce(`${job.title} marked as applied and moved to Applied.`);
  }

  function closeDialog(open: boolean) {
    if (!open && !saving) {
      setConfirming(false);
    }
  }

  const appliedOn = formatDate(job.applied_when);

  return (
    <>
      {applied ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <p className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
            <CircleCheck aria-hidden="true" className="size-4 text-success" />
            {appliedOn ? `Applied on ${appliedOn}` : "Applied"}
          </p>
          <Button asChild variant="outline">
            <a
              ref={postingLinkRef}
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink aria-hidden="true" />
              View posting
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          </Button>
        </div>
      ) : (
        <Button type="button" onClick={openPosting}>
          <Send aria-hidden="true" />
          Apply
        </Button>
      )}

      <Dialog open={confirming} onOpenChange={closeDialog}>
        <DialogContent
          onCloseAutoFocus={(event) => {
            // The Apply button is gone once applied; move focus to its replacement.
            if (justApplied.current) {
              justApplied.current = false;
              event.preventDefault();
              postingLinkRef.current?.focus();
            }
          }}
        >
          <DialogHeader>
            <DialogTitle>Did you apply?</DialogTitle>
            <DialogDescription>
              The posting for {job.title} opened in a new tab. Choose Yes only
              if you submitted an application, and the job moves to Applied.
            </DialogDescription>
          </DialogHeader>
          {error && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => closeDialog(false)}
              aria-disabled={saving || undefined}
            >
              No
            </Button>
            <Button
              type="button"
              onClick={confirmApplied}
              aria-disabled={saving || undefined}
            >
              {saving && (
                <LoaderCircle aria-hidden="true" className="animate-spin" />
              )}
              {saving ? "Saving…" : "Yes, I applied"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
