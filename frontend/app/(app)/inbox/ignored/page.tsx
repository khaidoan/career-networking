import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Ignored" };

export default function IgnoredPage() {
  return <PagePlaceholder title="Ignored" message="No ignored jobs." />;
}
