"use client";

import { useState } from "react";
import { LoaderCircle, Pencil, Trash2 } from "lucide-react";

import { CompanyForm } from "@/components/companies/company-form";
import { DeleteCompanyDialog } from "@/components/companies/delete-company-dialog";
import { useAnnounce } from "@/components/ui/announcer";
import { Button } from "@/components/ui/button";
import { getCompany, type CompanyDetail } from "@/lib/api/companies";
import { COMPANY_HAS_JOBS_MESSAGE } from "@/lib/companies/form";
import { cn } from "@/lib/utils";

type CompanyActionsProps = {
  company: { id: number; name: string };
  /**
   * The full company when it is already loaded (Company Details). Without it (a Companies
   * card) the company is loaded when Edit or Delete is chosen.
   */
  detail?: CompanyDetail | null;
  /** `icon` for cards (labelled icon buttons), `labeled` for the Company Details header. */
  variant: "icon" | "labeled";
  onSaved: (company: CompanyDetail) => void;
  onDeleted: () => void;
  className?: string;
};

type Pending = "edit" | "delete" | null;

/** Edit and Delete for one company, shared by the Companies cards and Company Details. */
export function CompanyActions({
  company,
  detail: loadedDetail = null,
  variant,
  onSaved,
  onDeleted,
  className,
}: CompanyActionsProps) {
  const announce = useAnnounce();
  const [fetched, setFetched] = useState<CompanyDetail | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [open, setOpen] = useState<Pending>(null);
  const detail = loadedDetail ?? fetched;

  // Company Details knows the job count up front, so Delete is disabled right on the page.
  const deleteBlocked = loadedDetail !== null && loadedDetail.job_count > 0;
  const reasonId = `company-${company.id}-delete-reason`;

  async function openWithDetail(action: "edit" | "delete") {
    if (pending) {
      return;
    }
    if (loadedDetail) {
      setOpen(action);
      return;
    }
    // A card only has the list fields; load the rest (and the job count) first.
    setPending(action);
    const result = await getCompany(company.id);
    setPending(null);
    if (!result.ok) {
      announce(`Could not load ${company.name}. ${result.message}`, "error");
      return;
    }
    setFetched(result.company);
    setOpen(action);
  }

  function handleSaved(saved: CompanyDetail) {
    setFetched(saved);
    onSaved(saved);
  }

  const labeled = variant === "labeled";
  const spinner = <LoaderCircle aria-hidden="true" className="animate-spin" />;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant={labeled ? "outline" : "ghost"}
          size={labeled ? "default" : "icon"}
          aria-label={labeled ? undefined : `Edit ${company.name}`}
          title={labeled ? undefined : "Edit"}
          aria-busy={pending === "edit" || undefined}
          onClick={() => void openWithDetail("edit")}
        >
          {pending === "edit" ? spinner : <Pencil aria-hidden="true" />}
          {labeled && "Edit"}
        </Button>
        <Button
          type="button"
          variant={labeled ? "outline" : "ghost"}
          size={labeled ? "default" : "icon"}
          aria-label={labeled ? undefined : `Delete ${company.name}`}
          title={labeled ? undefined : "Delete"}
          aria-busy={pending === "delete" || undefined}
          aria-disabled={deleteBlocked || undefined}
          aria-describedby={deleteBlocked ? reasonId : undefined}
          onClick={() => {
            if (!deleteBlocked) {
              void openWithDetail("delete");
            }
          }}
        >
          {pending === "delete" ? spinner : <Trash2 aria-hidden="true" />}
          {labeled && "Delete"}
        </Button>
      </div>
      {deleteBlocked && (
        <p id={reasonId} className="text-sm text-muted-foreground">
          {COMPANY_HAS_JOBS_MESSAGE}
        </p>
      )}

      {detail && (
        <>
          <CompanyForm
            open={open === "edit"}
            onOpenChange={(next) => setOpen(next ? "edit" : null)}
            company={detail}
            onSaved={handleSaved}
          />
          <DeleteCompanyDialog
            open={open === "delete"}
            onOpenChange={(next) => setOpen(next ? "delete" : null)}
            company={detail}
            onDeleted={onDeleted}
          />
        </>
      )}
    </div>
  );
}
