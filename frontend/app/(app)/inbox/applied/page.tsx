import type { Metadata } from "next";

import { InboxPage } from "@/components/jobs/inbox-page";

export const metadata: Metadata = { title: "Applied" };

export default function AppliedPage() {
  return <InboxPage inbox="applied" description="Jobs you have applied to." />;
}
