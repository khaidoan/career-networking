import type { Metadata } from "next";

import { InboxPage } from "@/components/jobs/inbox-page";
import { RequireProfileSetup } from "@/components/profile/require-profile-setup";

export const metadata: Metadata = { title: "Recommended" };

// The landing page: an incomplete profile is sent to the Profile page first.
export default function RecommendedPage() {
  return (
    <RequireProfileSetup>
      <InboxPage
        inbox="recommended"
        description="Jobs that match your preferences, liked jobs first, then newest."
      />
    </RequireProfileSetup>
  );
}
