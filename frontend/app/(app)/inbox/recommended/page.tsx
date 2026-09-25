import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Recommended" };

export default function RecommendedPage() {
  return (
    <PagePlaceholder title="Recommended" message="No recommended jobs yet." />
  );
}
