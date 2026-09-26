/** The four job inboxes: labels, page routes and empty-state copy. */

import type { InboxType } from "@/lib/api/jobs";

export const INBOX_LABELS: Readonly<Record<InboxType, string>> = {
  recommended: "Recommended",
  applied: "Applied",
  ignored: "Ignored",
  need_attention: "Need Attention",
};

/** Page routes use hyphens (`need-attention`); the API uses the stored slug (`need_attention`). */
export const INBOX_PATHS: Readonly<Record<InboxType, string>> = {
  recommended: "/inbox/recommended",
  applied: "/inbox/applied",
  ignored: "/inbox/ignored",
  need_attention: "/inbox/need-attention",
};

export const INBOX_EMPTY_STATES: Readonly<
  Record<InboxType, { title: string; message: string }>
> = {
  recommended: {
    title: "No recommended jobs yet",
    message:
      "Jobs that match your preferences appear here after the daily job search.",
  },
  applied: {
    title: "No applied jobs yet",
    message: "When you apply to a job and confirm it, the job moves here.",
  },
  ignored: {
    title: "No ignored jobs",
    message:
      "Jobs that score below your match threshold, or could not be scored, appear here.",
  },
  need_attention: {
    title: "Nothing needs your attention",
    message:
      "You're all caught up. Jobs that need your input will show up here.",
  },
};
