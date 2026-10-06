import type { Metadata } from "next";

import { PagePlaceholder } from "@/components/app-shell/page-placeholder";

export const metadata: Metadata = { title: "Feedback" };

const LINKEDIN_URL = "https://www.linkedin.com/in/khaidoan/";

export default function FeedbackPage() {
  return (
    <PagePlaceholder
      title="Feedback"
      message={
        <>
          Have feedback or ideas? Send them to me by contacting me on{" "}
          <a
            href={LINKEDIN_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-foreground underline underline-offset-4 hover:text-primary"
          >
            LinkedIn
          </a>
          .
        </>
      }
    />
  );
}
