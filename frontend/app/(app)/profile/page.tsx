import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Profile / Preferences" };

export default function ProfilePage() {
  return (
    <PagePlaceholder
      title="Profile / Preferences"
      message="Your profile and job preferences will appear here."
    />
  );
}
