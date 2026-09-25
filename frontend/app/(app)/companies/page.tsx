import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Companies" };

export default function CompaniesPage() {
  return <PagePlaceholder title="Companies" message="No companies yet." />;
}
