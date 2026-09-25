import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Prompts" };

export default function PromptsPage() {
  return <PagePlaceholder title="Prompts" message="No prompts yet." />;
}
