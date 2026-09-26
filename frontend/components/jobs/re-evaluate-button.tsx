"use client";

import { useState } from "react";
import { LoaderCircle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAnnounce } from "@/components/ui/announcer";
import { reEvaluateJob, type JobCard, type JobDetail } from "@/lib/api/jobs";
import { matchStrength } from "@/lib/jobs/format";
import { INBOX_LABELS } from "@/lib/jobs/inbox";

type ReEvaluateButtonProps = {
  job: Pick<JobCard, "id" | "title" | "inbox_type">;
  /** Receives the updated job, whether or not the new evaluation succeeded. */
  onEvaluated: (job: JobDetail) => void;
  className?: string;
};

/** The announcement for a finished re-evaluation (the API returns 200 even when it fails). */
export function describeReEvaluation(
  before: Pick<JobCard, "title" | "inbox_type">,
  after: JobDetail,
): string {
  if (after.evaluation_error) {
    return `${before.title} could not be scored: ${after.evaluation_error}`;
  }
  const score =
    after.overall_score === null
      ? ""
      : `: ${matchStrength(after.overall_score)} match, ${after.overall_score}`;
  const moved =
    after.inbox_type === before.inbox_type
      ? ""
      : ` Moved to ${INBOX_LABELS[after.inbox_type]}.`;
  return `${before.title} re-evaluated${score}.${moved}`;
}

/**
 * Runs the evaluator again for one job. While it runs the button stays focusable but reads
 * "Re-evaluating…" and ignores clicks; the outcome is announced.
 */
export function ReEvaluateButton({
  job,
  onEvaluated,
  className,
}: ReEvaluateButtonProps) {
  const announce = useAnnounce();
  const [running, setRunning] = useState(false);

  async function run() {
    if (running) {
      return;
    }
    setRunning(true);
    const result = await reEvaluateJob(job.id);
    setRunning(false);
    if (!result.ok) {
      announce(
        `Could not re-evaluate ${job.title}. ${result.message}`,
        "error",
      );
      return;
    }
    onEvaluated(result.job);
    announce(
      describeReEvaluation(job, result.job),
      result.job.evaluation_error ? "error" : "status",
    );
  }

  return (
    <Button
      type="button"
      variant="outline"
      aria-disabled={running || undefined}
      onClick={run}
      className={className}
    >
      {running ? (
        <LoaderCircle aria-hidden="true" className="animate-spin" />
      ) : (
        <RotateCw aria-hidden="true" />
      )}
      {running ? "Re-evaluating…" : "Re-evaluate"}
    </Button>
  );
}
