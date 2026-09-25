import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Feedback" };

export default function FeedbackPage() {
  return <PagePlaceholder title="Feedback" message="No feedback yet." />;
}
