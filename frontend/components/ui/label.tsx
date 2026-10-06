import * as React from "react";

import { cn } from "@/lib/utils";

// A native <label> rather than the Radix one: Radix cancels double-clicks on labels, which stops
// users from selecting the label text. Clicking still focuses the linked field.
function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium text-foreground peer-disabled:cursor-not-allowed peer-disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}

export { Label };
