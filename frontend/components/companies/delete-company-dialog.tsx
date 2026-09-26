"use client";

import { useState } from "react";
import { LoaderCircle, Trash2 } from "lucide-react";

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
import { deleteCompany, type CompanyDetail } from "@/lib/api/companies";
import { COMPANY_HAS_JOBS_MESSAGE } from "@/lib/companies/form";

type DeleteCompanyDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  company: Pick<CompanyDetail, "id" | "name" | "job_count" | "contacts">;
  /** Called after the company was deleted. */
  onDeleted: () => void;
};

function contactCount(count: number) {
  return `${count} ${count === 1 ? "contact" : "contacts"}`;
}

/**
 * Confirms deleting a company and warns that its contacts go with it. A company with jobs
 * cannot be deleted: Delete stays disabled with the reason (also shown after a server 409).
 */
export function DeleteCompanyDialog({
  open,
  onOpenChange,
  company,
  onDeleted,
}: DeleteCompanyDialogProps) {
  const announce = useAnnounce();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasJobs, setHasJobs] = useState(false);

  const blocked = company.job_count > 0 || hasJobs;
  const reasonId = `delete-company-${company.id}-reason`;

  async function confirmDelete() {
    if (deleting || blocked) {
      return;
    }
    setDeleting(true);
    setError(null);
    const result = await deleteCompany(company.id);
    setDeleting(false);
    if (!result.ok) {
      if (result.kind === "conflict") {
        setHasJobs(true);
        setError(COMPANY_HAS_JOBS_MESSAGE);
      } else {
        setError(result.message);
      }
      announce(`Could not delete ${company.name}. ${result.message}`, "error");
      return;
    }
    announce(`${company.name} deleted.`);
    onOpenChange(false);
    onDeleted();
  }

  function handleOpenChange(next: boolean) {
    if (deleting) {
      return;
    }
    if (!next) {
      setError(null);
    }
    onOpenChange(next);
  }

  const contacts = company.contacts.length;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete {company.name}?</DialogTitle>
          <DialogDescription>
            {contacts > 0
              ? `Its ${contactCount(contacts)} will be deleted too. This can't be undone.`
              : "Its contacts will be deleted too. This can't be undone."}
          </DialogDescription>
        </DialogHeader>
        {blocked ? (
          <p id={reasonId} className="text-sm font-medium text-foreground">
            {COMPANY_HAS_JOBS_MESSAGE}
          </p>
        ) : (
          error && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {error}
            </p>
          )
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={confirmDelete}
            disabled={blocked}
            aria-disabled={deleting || undefined}
            aria-describedby={blocked ? reasonId : undefined}
          >
            {deleting ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" />
            ) : (
              <Trash2 aria-hidden="true" />
            )}
            {deleting ? "Deleting…" : "Delete company"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
