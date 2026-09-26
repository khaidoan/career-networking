import type { Metadata } from "next";

import { InboxPage } from "@/components/jobs/inbox-page";

export const metadata: Metadata = { title: "Ignored" };

export default function IgnoredPage() {
  return (
    <InboxPage
      inbox="ignored"
      description="Jobs below your match threshold, and jobs that could not be scored."
    />
  );
}
