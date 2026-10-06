"use client";

import { MessageSquareText } from "lucide-react";

import { MatchStrengthBadge } from "@/components/jobs/match-indicators";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { JobCard } from "@/lib/api/jobs";
import { cn } from "@/lib/utils";

type ScoreExplanationDialogProps = {
  job: Pick<
    JobCard,
    "title" | "company_name" | "overall_score" | "score_explanation"
  >;
  className?: string;
};

/** "View Explanation" button that opens the model's reason for the job's overall score. */
export function ScoreExplanationDialog({
  job,
  className,
}: ScoreExplanationDialogProps) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className={className}>
          <MessageSquareText aria-hidden="true" />
          View Explanation
          <span className="sr-only"> for {job.title}</span>
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Why this job scored low</DialogTitle>
          <DialogDescription>
            {job.title} at {job.company_name}
          </DialogDescription>
        </DialogHeader>
        {job.overall_score !== null && (
          <MatchStrengthBadge score={job.overall_score} />
        )}
        <p
          className={cn(
            "text-sm leading-relaxed whitespace-pre-line",
            job.score_explanation ? "text-foreground" : "text-muted-foreground",
          )}
        >
          {job.score_explanation ?? "No explanation was saved for this job."}
        </p>
        <DialogFooter>
          <DialogClose asChild>
            <Button>Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
