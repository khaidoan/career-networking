import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Need Attention" };

export default function NeedAttentionPage() {
  return (
    <PagePlaceholder
      title="Need Attention"
      message="Nothing needs your attention right now."
    />
  );
}
