"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { SetupItem } from "@/lib/profile/form";

const SETUP_ITEM_LABELS: Record<SetupItem, string> = {
  resume: "Upload your resume (PDF or Word).",
  desired_titles: "Add at least one desired job title.",
  country: "Choose the country you want to work in.",
};

type SetupDialogProps = {
  open: boolean;
  onClose: () => void;
  /** What is still missing; listed in this order. */
  missing: SetupItem[];
};

/** Shown on the Profile page until the resume, desired titles and country are all provided. */
export function SetupDialog({ open, onClose, missing }: SetupDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Finish setting up your profile</DialogTitle>
          <DialogDescription>
            Jobs are found and scored from your resume and preferences. Before
            you can see recommended jobs:
          </DialogDescription>
        </DialogHeader>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
          {missing.map((item) => (
            <li key={item}>{SETUP_ITEM_LABELS[item]}</li>
          ))}
        </ul>
        {missing.some((item) => item !== "resume") && (
          <p className="text-sm text-muted-foreground">
            Then click Save at the bottom of the page.
          </p>
        )}
        <DialogFooter className="sm:justify-center">
          <Button type="button" onClick={onClose}>
            Ok
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
