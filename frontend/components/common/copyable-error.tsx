"use client";

import { useState } from "react";
import { Check, Copy, TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { copyText } from "@/lib/outreach/clipboard";
import { cn } from "@/lib/utils";

type CopyableErrorProps = {
  title: string;
  message: string;
  className?: string;
};

/**
 * An error that stays on the page until the next attempt, with selectable text and a Copy
 * button (title and message together), so it can be pasted into a bug report.
 */
export function CopyableError({
  title,
  message,
  className,
}: CopyableErrorProps) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    setCopied(await copyText(`${title} ${message}`));
  }

  return (
    <Alert variant="destructive" className={cn("select-text", className)}>
      <TriangleAlert aria-hidden="true" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="flex flex-col items-start gap-2">
        <p className="break-words text-foreground">{message}</p>
        <Button type="button" variant="outline" size="sm" onClick={copy}>
          {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copied ? "Copied" : "Copy error"}
        </Button>
      </AlertDescription>
    </Alert>
  );
}
