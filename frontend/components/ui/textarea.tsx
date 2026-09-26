import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-24 w-full min-w-0 rounded-lg border border-input bg-surface px-3 py-2 text-base text-foreground shadow-soft-sm transition-colors placeholder:text-muted-foreground focus-visible:border-accent disabled:cursor-not-allowed disabled:bg-surface-alt disabled:opacity-60 aria-invalid:border-destructive md:text-sm",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
