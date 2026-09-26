import type { Metadata } from "next";

import { InboxPage } from "@/components/jobs/inbox-page";

export const metadata: Metadata = { title: "Need Attention" };

export default function NeedAttentionPage() {
  return (
    <InboxPage
      inbox="need_attention"
      description="Jobs that need your input before they can move forward."
    />
  );
}
