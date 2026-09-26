import type { Metadata } from "next";

import { InboxPage } from "@/components/jobs/inbox-page";

export const metadata: Metadata = { title: "Recommended" };

export default function RecommendedPage() {
  return (
    <InboxPage
      inbox="recommended"
      description="Jobs that match your preferences, liked jobs first, then newest."
    />
  );
}
