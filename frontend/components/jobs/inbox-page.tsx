import { Suspense } from "react";

import { JobList } from "@/components/jobs/job-list";
import type { InboxType } from "@/lib/api/jobs";
import { INBOX_LABELS } from "@/lib/jobs/inbox";

type InboxPageProps = {
  inbox: InboxType;
  description: string;
};

/** Page layout shared by the four inboxes: the page heading and the job list. */
export function InboxPage({ inbox, description }: InboxPageProps) {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          {INBOX_LABELS[inbox]}
        </h1>
        <p className="text-muted-foreground">{description}</p>
      </header>
      {/* The list reads its filters from the URL, which is only known in the browser. */}
      <Suspense
        fallback={
          <p role="status" className="text-sm text-muted-foreground">
            Loading jobs…
          </p>
        }
      >
        <JobList inbox={inbox} />
      </Suspense>
    </div>
  );
}
