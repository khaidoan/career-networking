import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Interview Tips" };

export default function InterviewTipsPage() {
  return (
    <PagePlaceholder title="Interview Tips" message="No interview tips yet." />
  );
}
