import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Applied" };

export default function AppliedPage() {
  return (
    <PagePlaceholder
      title="Applied"
      message="You haven't applied to any jobs yet."
    />
  );
}
