"use client";

import { useId, useState } from "react";
import { ExternalLink, LoaderCircle, UserSearch } from "lucide-react";

import { CopyableError } from "@/components/common/copyable-error";
import { Button } from "@/components/ui/button";
import { useAnnounce } from "@/components/ui/announcer";
import {
  findContacts,
  type ContactSearchResult,
  type ContactSearchStatus,
} from "@/lib/api/contacts";
import {
  CONTACT_SEARCH_UNAVAILABLE_MESSAGES,
  describeContactSearch,
} from "@/lib/contacts/search";
import { cn } from "@/lib/utils";

type FindContactsButtonProps = {
  companyId: number;
  /** The job whose title is searched for (Job Details); omitted on Company Details. */
  jobId?: number;
  status: ContactSearchStatus;
  /** Receives the company's full contact list and the new status after a successful search. */
  onFound: (result: ContactSearchResult) => void;
  /** The company's LinkedIn "People" page; adds a "Browse on LinkedIn" button. */
  peopleUrl?: string | null;
  className?: string;
};

type Outcome = { kind: "result" | "error"; message: string } | null;

/**
 * Runs one contact search (a Google search plus one AI pick) for a company, next to an optional
 * "Browse on LinkedIn" link. Nothing is ever sent to LinkedIn. While it runs, or when
 * search is unavailable, the button stays focusable with `aria-disabled` and ignores clicks; an
 * unavailable button is described by a visible explanation. The outcome is announced and stays
 * below the buttons (an error with a Copy button) until the next search.
 */
export function FindContactsButton({
  companyId,
  jobId,
  status,
  onFound,
  peopleUrl,
  className,
}: FindContactsButtonProps) {
  const announce = useAnnounce();
  const reasonId = useId();
  const [running, setRunning] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const reason = status.available ? null : status.unavailable_reason;
  const unavailable = !status.available;

  async function run() {
    if (running || unavailable) {
      return;
    }
    setRunning(true);
    setOutcome(null);
    const result = await findContacts(companyId, jobId);
    setRunning(false);
    if (!result.ok) {
      setOutcome({ kind: "error", message: result.message });
      announce(`Could not find contacts. ${result.message}`, "error");
      return;
    }
    onFound(result.result);
    const message = describeContactSearch(result.result);
    setOutcome({ kind: "result", message });
    announce(message);
  }

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          aria-disabled={running || unavailable || undefined}
          aria-describedby={unavailable ? reasonId : undefined}
          onClick={run}
        >
          {running ? (
            <LoaderCircle aria-hidden="true" className="animate-spin" />
          ) : (
            <UserSearch aria-hidden="true" />
          )}
          {running ? "Searching…" : "Find contacts"}
        </Button>
        {peopleUrl && (
          <Button asChild variant="outline">
            <a href={peopleUrl} target="_blank" rel="noopener noreferrer">
              <ExternalLink aria-hidden="true" />
              Browse on LinkedIn
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          </Button>
        )}
      </div>
      {unavailable && (
        <p id={reasonId} className="text-sm text-muted-foreground">
          {reason
            ? CONTACT_SEARCH_UNAVAILABLE_MESSAGES[reason]
            : "Contact search is not available right now."}
        </p>
      )}
      {outcome?.kind === "result" && (
        <p className="text-sm text-muted-foreground">{outcome.message}</p>
      )}
      {outcome?.kind === "error" && (
        <CopyableError
          title="Could not find contacts."
          message={outcome.message}
        />
      )}
    </div>
  );
}
