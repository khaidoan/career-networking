"use client";

import { useId, useState } from "react";
import { LoaderCircle, UserSearch } from "lucide-react";

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
import { formatDateTime, formatRelativeTime } from "@/lib/jobs/format";
import { cn } from "@/lib/utils";

type FindContactsButtonProps = {
  companyId: number;
  /** The job whose title is searched for (Job Details); omitted on Company Details. */
  jobId?: number;
  status: ContactSearchStatus;
  /** Receives the company's full contact list and the new status after a successful search. */
  onFound: (result: ContactSearchResult) => void;
  className?: string;
};

/** "Last searched 3 days ago" with the full date and time on hover, or "Not searched yet". */
function LastSearched({ iso }: { iso: string | null }) {
  const relative = formatRelativeTime(iso);
  if (!iso || !relative) {
    return <p className="text-sm text-muted-foreground">Not searched yet</p>;
  }
  return (
    <p className="text-sm text-muted-foreground">
      Last searched{" "}
      <time dateTime={iso} title={formatDateTime(iso) ?? undefined}>
        {relative}
      </time>
    </p>
  );
}

/**
 * Runs one contact search (a Google search plus one AI pick) for a company. Nothing is ever
 * sent to LinkedIn. While it runs, or when search is unavailable, the button stays focusable
 * with `aria-disabled` and ignores clicks; an unavailable button is described by a visible
 * explanation. The outcome is announced.
 */
export function FindContactsButton({
  companyId,
  jobId,
  status,
  onFound,
  className,
}: FindContactsButtonProps) {
  const announce = useAnnounce();
  const reasonId = useId();
  const [running, setRunning] = useState(false);
  const reason = status.available ? null : status.unavailable_reason;
  const unavailable = !status.available;

  async function run() {
    if (running || unavailable) {
      return;
    }
    setRunning(true);
    const result = await findContacts(companyId, jobId);
    setRunning(false);
    if (!result.ok) {
      announce(`Could not find contacts. ${result.message}`, "error");
      return;
    }
    onFound(result.result);
    announce(describeContactSearch(result.result));
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
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
        <LastSearched iso={status.last_searched_at} />
      </div>
      {unavailable && (
        <p id={reasonId} className="text-sm text-muted-foreground">
          {reason
            ? CONTACT_SEARCH_UNAVAILABLE_MESSAGES[reason]
            : "Contact search is not available right now."}
        </p>
      )}
    </div>
  );
}
